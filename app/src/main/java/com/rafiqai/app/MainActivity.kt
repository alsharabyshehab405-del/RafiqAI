package com.rafiqai.app

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.provider.OpenableColumns
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.rafiqai.app.data.local.*
import com.rafiqai.app.data.network.*
import kotlinx.coroutines.launch
import androidx.lifecycle.viewmodel.compose.viewModel
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.Locale
import java.time.Instant

@Composable private fun tr(language: String, id: Int, vararg args: Any): String = androidx.compose.ui.res.stringResource(id, *args)

@Composable
fun RafiqTheme(dark: Boolean, content: @Composable () -> Unit) = MaterialTheme(colorScheme = if (dark) darkColorScheme() else lightColorScheme(), content = content)

class MainActivity : ComponentActivity() {
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        val app = application as RafiqApplication
        RafiqNotifications.createChannel(this)
        setContent { Root(app, notificationPermission) }
    }
}

@Composable
fun Root(app: RafiqApplication, notificationPermission: androidx.activity.result.ActivityResultLauncher<String>) {
    val prefs = remember { app.preferences }
    val scope = rememberCoroutineScope()
    val onboarded by prefs.onboardingDone.collectAsState(false)
    val dark by prefs.dark.collectAsState(false)
    val language by prefs.language.collectAsState("ar")
    var token by remember { mutableStateOf(app.session.access()) }
    CompositionLocalProvider(LocalLayoutDirection provides if (language == "ar") LayoutDirection.Rtl else LayoutDirection.Ltr) {
        RafiqTheme(dark) {
            when {
                !onboarded -> Onboarding(language) { scope.launch { prefs.setOnboardingDone(true) } }
                token == null -> Auth(language) { access, refresh -> app.session.save(access, refresh); token = access }
                else -> Home(app, language, dark, { scope.launch { prefs.setDark(it) } }, { scope.launch { prefs.setLanguage(it) } }, notificationPermission) { app.session.clear(); token = null }
            }
        }
    }
}

@Composable
fun Onboarding(language: String, done: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Rafiq AI", style = MaterialTheme.typography.displaySmall)
        Text(tr(language, R.string.your_personal_ai_assistant), style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text(tr(language, R.string.chat_memory_tasks_and_secure_cross_device_syn))
        Spacer(Modifier.height(24.dp))
        Button(done, Modifier.fillMaxWidth()) { Text(tr(language, R.string.get_started)) }
    }
}

@Composable
fun Auth(language: String, onSuccess: (String, String) -> Unit) {
    var email by remember { mutableStateOf("") }; var pass by remember { mutableStateOf("") }; var register by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }; var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope(); val app = LocalContext.current.applicationContext as RafiqApplication
    val api = remember { ApiClientFactory.create(app.session) }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Rafiq AI", style = MaterialTheme.typography.displaySmall); Spacer(Modifier.height(20.dp))
        OutlinedTextField(email, { email = it }, label = { Text(tr(language, R.string.email)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email), singleLine = true)
        Spacer(Modifier.height(8.dp)); OutlinedTextField(pass, { pass = it }, label = { Text(tr(language, R.string.password)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), singleLine = true)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }; Spacer(Modifier.height(8.dp))
        Button(enabled = !busy && email.isNotBlank() && pass.length >= 8, onClick = { scope.launch { busy = true; error = null; runCatching { if (register) api.register(AuthBody(email.trim(), pass)) else api.login(AuthBody(email.trim(), pass)) }.onSuccess { onSuccess(it.access_token, it.refresh_token) }.onFailure { error = tr(language, R.string.could_not_complete_the_request_check_your_det) }; busy = false } }, Modifier.fillMaxWidth()) { Text(if (busy) tr(language, R.string.connecting) else if (register) tr(language, R.string.create_account) else tr(language, R.string.sign_in)) }
        TextButton({ register = !register }) { Text(if (register) tr(language, R.string.i_already_have_an_account) else tr(language, R.string.create_an_account)) }
    }
}

@Composable
fun Home(app: RafiqApplication, language: String, dark: Boolean, onDark: (Boolean) -> Unit, onLanguage: (String) -> Unit, notificationPermission: androidx.activity.result.ActivityResultLauncher<String>, onLogout: () -> Unit) {
    val db = app.database; val api = remember { ApiClientFactory.create(app.session) }; val scope = rememberCoroutineScope()
    var tab by remember { mutableStateOf(0) }; val snackbarHostState = remember { SnackbarHostState() }; var selected by remember { mutableStateOf<Long?>(null) }; var showProfile by remember { mutableStateOf(false) }; var showSearch by remember { mutableStateOf(false) }
    var conversations by remember { mutableStateOf<List<ConversationEntity>>(emptyList()) }; var tasks by remember { mutableStateOf<List<TaskEntity>>(emptyList()) }; var snackbar by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { db.conversations().observe().collect { conversations = it } }
    LaunchedEffect(Unit) { db.tasks().observe().collect { tasks = it } }
    LaunchedEffect(Unit) { runCatching { val sync = api.sync(); sync.conversations.forEach { db.conversations().upsert(ConversationEntity(it.id, it.title, System.currentTimeMillis())) }; sync.messages.forEach { db.messages().upsert(MessageEntity(it.id, it.conversation_id, it.role, it.content, System.currentTimeMillis())) }; sync.tasks.forEach { db.tasks().upsert(TaskEntity(it.id, it.title, it.description, it.completed, it.due_at?.let { due -> runCatching { Instant.parse(due).toEpochMilli() }.getOrNull() }, it.priority, it.recurrence, System.currentTimeMillis())) } }.onFailure { scope.launch { snackbarHostState.showSnackbar(tr(language, R.string.offline_mode_local_data_is_being_used)) } } }
    LaunchedEffect(Unit) { runCatching { com.google.firebase.messaging.FirebaseMessaging.getInstance().token.addOnSuccessListener { token -> scope.launch { runCatching { api.registerFcm(DeviceTokenBody(token)) } } } } }
    if (showProfile) ProfileDialog(app, api, language, onLogout) { showProfile = false }
    if (showSearch) SearchDialog(api, language) { selected = it; showSearch = false }
    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = { NavigationBar { NavigationBarItem(tab == 0, { tab = 0 }, { Icon(Icons.Default.Chat, null) }, label = { Text(tr(language, R.string.chat)) }); NavigationBarItem(tab == 1, { tab = 1 }, { Icon(Icons.Default.CheckCircle, null) }, label = { Text(tr(language, R.string.tasks)) }); NavigationBarItem(tab == 2, { tab = 2 }, { Icon(Icons.Default.Settings, null) }, label = { Text(tr(language, R.string.settings)) }); NavigationBarItem(tab == 3, { tab = 3 }, { Icon(Icons.Default.Workspaces, null) }, label = { Text(if(language=="ar") "مساحة العمل" else "Workspace") }) } },
        topBar = { TopAppBar(title = { Text(if (tab == 0) "Rafiq AI" else if (tab == 1) tr(language, R.string.tasks) else if (tab == 2) tr(language, R.string.settings) else if(language=="ar") "مساحة العمل" else "Workspace") }, actions = { if (tab == 0) IconButton({ showSearch = true }) { Icon(Icons.Default.Search, tr(language, R.string.search)) }; IconButton({ showProfile = true }) { Icon(Icons.Default.Person, null) } }) }
    ) { pad -> when (tab) { 0 -> ChatTab(db, api, conversations, selected, { selected = it }, language, notificationPermission, Modifier.padding(pad)); 1 -> TasksTab(db, api, tasks, language, notificationPermission, Modifier.padding(pad)); 2 -> SettingsTab(app, api, dark, onDark, language, onLanguage, notificationPermission, { scope.launch { runCatching { api.logout(RefreshBody(app.session.refresh() ?: "")) }; onLogout() } }, Modifier.padding(pad)); 3 -> ProductWorkspace(app, api, language, Modifier.padding(pad)) } }
}

@Composable
fun ChatTab(db: RafiqDatabase, api: RafiqApi, items: List<ConversationEntity>, selected: Long?, select: (Long) -> Unit, language: String, notificationPermission: androidx.activity.result.ActivityResultLauncher<String>, mod: Modifier) {
    val scope = rememberCoroutineScope(); val context = LocalContext.current; var input by remember { mutableStateOf("") }; var messages by remember { mutableStateOf<List<MessageEntity>>(emptyList()) }; var loading by remember { mutableStateOf(false) }; var menu by remember { mutableStateOf<Long?>(null) }; var rename by remember { mutableStateOf<ConversationEntity?>(null) }; var newTitle by remember { mutableStateOf("") }
    val fileLauncher = androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { selectedUri -> scope.launch { runCatching { context.contentResolver.openInputStream(selectedUri)?.use { stream -> val bytes = stream.readBytes(); val cursor=context.contentResolver.query(selectedUri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null); val name=cursor?.use{if(it.moveToFirst())it.getString(0)else null} ?: "upload"; val mime=context.contentResolver.getType(selectedUri) ?: "application/octet-stream"; val body=bytes.toRequestBody(mime.toMediaType()); api.uploadFile(okhttp3.MultipartBody.Part.createFormData("file",name,body), selected) } }.onFailure { /* user-visible error can be surfaced by snackbar */ } } } }
    var speaking by remember { mutableStateOf(false) }
    LaunchedEffect(selected, items) { if (selected == null && items.isNotEmpty()) select(items.first().id); val c = items.firstOrNull { it.id == selected } ?: items.firstOrNull(); c?.let { runCatching { api.messages(it.id).items.forEach { d -> db.messages().upsert(MessageEntity(d.id, d.conversation_id, d.role, d.content, System.currentTimeMillis())) } }; messages = db.messages().page(it.id, 100, 0) } }
    Column(mod.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { scope.launch { runCatching { api.createConversation(ConversationCreate(tr(language, R.string.new_conversation))) }.onSuccess { db.conversations().upsert(ConversationEntity(it.id, it.title, System.currentTimeMillis())); select(it.id) } } }) { Icon(Icons.Default.Add, null); Text(tr(language, R.string.chat_2)) }
            LazyColumn(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(2.dp)) { items(items) { c -> Row(verticalAlignment = Alignment.CenterVertically) { TextButton({ select(c.id) }) { Text(c.title, maxLines = 1) }; IconButton({ menu = c.id }) { Icon(Icons.Default.MoreVert, null) }; DropdownMenu(menu == c.id, { menu = null }) { DropdownMenuItem({ Text(tr(language, R.string.rename)) }, { newTitle = c.title; rename = c; menu = null }); DropdownMenuItem({ Text(tr(language, R.string.delete)) }, { scope.launch { runCatching { api.deleteConversation(c.id) }; db.messages().deleteForConversation(c.id); db.conversations().delete(c.id); if (selected == c.id) select(items.firstOrNull { it.id != c.id }?.id ?: -1) }; menu = null }) } } } }
        }
        val current = items.firstOrNull { it.id == selected } ?: items.firstOrNull()
        current?.let { c ->
            LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(messages) { m -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(10.dp)) { Text(if (m.role == "user") tr(language, R.string.you) else "Rafiq AI", style = MaterialTheme.typography.labelMedium); Text(m.content); Row { IconButton({ context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Rafiq", m.content)) }) { Icon(Icons.Default.ContentCopy, null) }; IconButton({ share(context, m.content) }) { Icon(Icons.Default.Share, null) }; IconButton({ if (speaking) { RafiqTts.stop(); speaking = false } else { RafiqTts.speak(context, m.content, if (language == "ar") Locale("ar") else Locale.US); speaking = true } }) { Icon(if (speaking) Icons.Default.Stop else Icons.Default.VolumeUp, txt(language, "إيقاف القراءة", "Stop reading")) }; IconButton({ scope.launch { runCatching { api.deleteMessage(c.id, m.id) }; db.messages().delete(m.id); messages = messages.filterNot { it.id == m.id } } }) { Icon(Icons.Default.Delete, null) } } } } }
            }
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { fileLauncher.launch(arrayOf("application/pdf", "text/plain", "text/csv", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "image/*")) }) { Icon(Icons.Default.AttachFile, tr(language, R.string.attach_file)) }
                VoiceInputButton(language) { input = if (input.isBlank()) it else "$input $it" }
                OutlinedTextField(input, { input = it }, Modifier.weight(1f), placeholder = { Text(tr(language, R.string.message_rafiq)) })
                FilledIconButton(enabled = !loading && input.isNotBlank(), onClick = { val text = input.trim(); input = ""; scope.launch { loading = true; val tempUser = MessageEntity(-System.currentTimeMillis(), c.id, "user", text, System.currentTimeMillis(), false); messages = messages + tempUser; var answer = ""; runCatching { StreamingClient((context.applicationContext as RafiqApplication).session).message(c.id, text).collect { chunk -> answer += chunk; messages = messages.filterNot { it.id == -1L } + MessageEntity(-1L, c.id, "assistant", answer, System.currentTimeMillis(), false) } }.onSuccess { runCatching { api.messages(c.id).items.forEach { d -> db.messages().upsert(MessageEntity(d.id, d.conversation_id, d.role, d.content, System.currentTimeMillis())) } }; messages = db.messages().page(c.id, 100, 0); if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) RafiqNotifications.show(context, "Rafiq AI", tr(language, R.string.new_ai_response)) }.onFailure { input = text; messages = messages.filterNot { it.id == tempUser.id || it.id == -1L } }; loading = false } }) { Icon(if (loading) Icons.Default.HourglassTop else Icons.Default.Send, null) }
            }
        }
    }
    rename?.let { r -> AlertDialog(onDismissRequest = { rename = null }, title = { Text(tr(language, R.string.rename)) }, text = { OutlinedTextField(newTitle, { newTitle = it }) }, confirmButton = { TextButton({ scope.launch { runCatching { api.renameConversation(r.id, ConversationUpdate(newTitle.trim())) }.onSuccess { db.conversations().upsert(ConversationEntity(it.id, it.title, System.currentTimeMillis())); rename = null } } }) { Text(tr(language, R.string.save)) } }, dismissButton = { TextButton({ rename = null }) { Text(tr(language, R.string.cancel)) } }) }
}

@Composable
fun TasksTab(db: RafiqDatabase, api: RafiqApi, tasks: List<TaskEntity>, language: String, notificationPermission: androidx.activity.result.ActivityResultLauncher<String>, mod: Modifier) {
    val scope = rememberCoroutineScope(); val context = LocalContext.current; var title by remember { mutableStateOf("") }; var priority by remember { mutableStateOf("normal") }; var dueMillis by remember { mutableStateOf<Long?>(null) }; var priorityMenu by remember { mutableStateOf(false) }
    Column(mod.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(title, { title = it }, Modifier.weight(1f), placeholder = { Text(tr(language, R.string.new_task)) })
            Box { Button({ priorityMenu = true }) { Text(priority) }; DropdownMenu(priorityMenu, { priorityMenu = false }) { listOf("low","normal","high","urgent").forEach { p -> DropdownMenuItem({ Text(p) }, { priority = p; priorityMenu = false }) } } }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button({ val cal = java.util.Calendar.getInstance(); android.app.DatePickerDialog(context, { _, y, m, d -> android.app.TimePickerDialog(context, { _, h, min -> cal.set(y,m,d,h,min,0); cal.set(java.util.Calendar.MILLISECOND,0); dueMillis = cal.timeInMillis }, cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE), true).show() }, cal.get(java.util.Calendar.YEAR), cal.get(java.util.Calendar.MONTH), cal.get(java.util.Calendar.DAY_OF_MONTH)).show() }) { Text(if (dueMillis == null) tr(language, R.string.due_date) else java.text.DateFormat.getDateTimeInstance().format(java.util.Date(dueMillis!!))) }
            Button(enabled = title.isNotBlank(), onClick = { scope.launch { runCatching { api.createTask(TaskCreate(title.trim(), priority = priority, due_at = dueMillis?.let { Instant.ofEpochMilli(it).toString() })) }.onSuccess { db.tasks().upsert(TaskEntity(it.id,it.title,it.description,it.completed,it.due_at?.let { due -> runCatching { Instant.parse(due).toEpochMilli() }.getOrNull() },it.priority,it.recurrence,System.currentTimeMillis())); title="";dueMillis=null } } }) { Text(tr(language, R.string.add)) }
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) { items(tasks) { t -> Card(Modifier.fillMaxWidth()) { Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) { Checkbox(t.completed, { scope.launch { runCatching { api.updateTask(t.id, TaskUpdate(completed = !t.completed)) }.onSuccess { db.tasks().upsert(TaskEntity(it.id,it.title,it.description,it.completed,it.due_at?.let { due -> runCatching { Instant.parse(due).toEpochMilli() }.getOrNull() },it.priority,it.recurrence,System.currentTimeMillis())) } } }); Column(Modifier.weight(1f)) { Text(t.title); Text("${t.priority}${t.dueAt?.let { " • "+java.text.DateFormat.getDateTimeInstance().format(java.util.Date(it)) } ?: ""}", style=MaterialTheme.typography.labelSmall) }; IconButton({ scope.launch { runCatching { api.deleteTask(t.id) }; db.tasks().delete(t.id) } }) { Icon(Icons.Default.Delete, tr(language, R.string.delete)) } } } } }
    }
}

@Composable
fun SettingsTab(app: RafiqApplication, api: RafiqApi, dark: Boolean, onDark: (Boolean) -> Unit, language: String, onLanguage: (String) -> Unit, notificationPermission: androidx.activity.result.ActivityResultLauncher<String>, onLogout: () -> Unit, mod: Modifier) {
    val scope = rememberCoroutineScope()
    var showMemory by remember { mutableStateOf(false) }
    if (showMemory) MemoryDialog(api, language) { showMemory = false }
    Column(mod.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Text(tr(language, R.string.dark_mode), Modifier.weight(1f)); Switch(dark, onDark) }
        Row(verticalAlignment = Alignment.CenterVertically) { Text(tr(language, R.string.language), Modifier.weight(1f)); TextButton({ onLanguage(if (language == "ar") "en" else "ar") }) { Text(if (language == "ar") "English" else "العربية") } }
        Text(tr(language, R.string.rafiq_ai_caches_data_locally_and_synchronizes))
        var memoryEnabled by remember { mutableStateOf(false) }
        var plan by remember { mutableStateOf("free") }; var analyticsEnabled by remember { mutableStateOf(true) }
        LaunchedEffect(Unit) { runCatching { api.profile() }.onSuccess { memoryEnabled = it.memory_enabled; analyticsEnabled = it.analytics_enabled; plan = it.plan } }
        Row(verticalAlignment = Alignment.CenterVertically) { Text(tr(language, R.string.rafiq_memory), Modifier.weight(1f)); Switch(memoryEnabled, { memoryEnabled = it; scope.launch { runCatching { api.memorySettings(com.rafiqai.app.data.network.MemorySettingsBody(it)) } } }) }
        Button(enabled = memoryEnabled, onClick = { showMemory = true }) { Text(tr(language, R.string.manage_memory)) }
        Row(verticalAlignment = Alignment.CenterVertically) { Text(tr(language, R.string.analytics_privacy), Modifier.weight(1f)); Switch(analyticsEnabled, { analyticsEnabled = it; scope.launch { runCatching { api.updateProfile(ProfileUpdate(locale = language, memory_enabled = memoryEnabled, analytics_enabled = it)) } } }) }
        Text(tr(language, R.string.current_plan_plan, plan), style = MaterialTheme.typography.labelLarge)
        Button({ val manager = BillingManager(app, scope); manager.connect { manager.queryProducts(listOf("rafiq_pro_monthly", "rafiq_premium_monthly")) {} } }) { Text(tr(language, R.string.subscriptions)) }
        if (android.os.Build.VERSION.SDK_INT >= 33) Button({ notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS) }) { Text(tr(language, R.string.enable_notifications)) }
        TextButton(onLogout) { Text(tr(language, R.string.sign_out)) }
    }
}

@Composable
fun ProfileDialog(app: RafiqApplication, api: RafiqApi, language: String, onLogout: () -> Unit, close: () -> Unit) {
    val scope = rememberCoroutineScope(); var name by remember { mutableStateOf("") }; var email by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { runCatching { api.profile() }.onSuccess { name = it.display_name; email = it.email } }
    AlertDialog(onDismissRequest = close, title = { Text(tr(language, R.string.account)) }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { Text(email); OutlinedTextField(name, { name = it }, label = { Text(tr(language, R.string.name)) }); Button({ scope.launch { runCatching { api.updateProfile(ProfileUpdate(name.trim(), language)) }; close() } }) { Text(tr(language, R.string.save_profile)) }; Button({ scope.launch { runCatching { api.deleteAccount() }; app.database.clearAll(); app.session.clear(); onLogout() } }) { Text(tr(language, R.string.delete_account)) } } }, confirmButton = { TextButton(close) { Text(tr(language, R.string.close)) } })
}

@Composable
fun MemoryDialog(api: RafiqApi, language: String, close: () -> Unit) {
    val scope = rememberCoroutineScope(); var memories by remember { mutableStateOf<List<MemoryDto>>(emptyList()) }; var key by remember { mutableStateOf("") }; var value by remember { mutableStateOf("") }; var editingId by remember { mutableStateOf<Long?>(null) }
    LaunchedEffect(Unit) { runCatching { api.memories() }.onSuccess { memories = it } }
    AlertDialog(onDismissRequest = close, title = { Text(tr(language, R.string.rafiq_memory)) }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        LazyColumn(Modifier.heightIn(max = 280.dp)) { items(memories) { m -> Card(Modifier.fillMaxWidth()) { Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text(m.key, style = MaterialTheme.typography.labelMedium); Text(m.value, maxLines = 3) }; IconButton({ key = m.key; value = m.value; editingId = m.id }) { Icon(Icons.Default.Edit, tr(language, R.string.edit)) }
                        IconButton({ scope.launch { runCatching { api.deleteMemory(m.id) }; memories = memories.filterNot { it.id == m.id } } }) { Icon(Icons.Default.Delete, tr(language, R.string.delete)) } } } } }
        OutlinedTextField(key, { key = it }, label = { Text(tr(language, R.string.memory_key)) })
        OutlinedTextField(value, { value = it }, label = { Text(tr(language, R.string.memory_value)) })
        Button(enabled = key.isNotBlank() && value.isNotBlank(), onClick = { scope.launch { runCatching { editingId?.let { api.updateMemory(it, MemoryBody(key.trim(), value.trim())) } ?: api.createMemory(MemoryBody(key.trim(), value.trim())) }.onSuccess { result -> memories = listOf(result) + memories.filterNot { it.id == result.id }; key = ""; value = ""; editingId = null } } }) { Text(if (editingId == null) tr(language, R.string.add_memory) else tr(language, R.string.save)) }
    } }, confirmButton = { TextButton(close) { Text(tr(language, R.string.close)) } })
}

@Composable
fun SearchDialog(api: RafiqApi, language: String, onOpen: (Long) -> Unit) {
    var q by remember { mutableStateOf("") }; var results by remember { mutableStateOf<List<SearchResultDto>>(emptyList()) }; val scope = rememberCoroutineScope()
    AlertDialog(onDismissRequest = { onOpen(-1) }, title = { Text(tr(language, R.string.search_conversations)) }, text = { Column { OutlinedTextField(q, { q = it }, singleLine = true); Button({ scope.launch { runCatching { api.search(q) }.onSuccess { results = it } } }) { Text(tr(language, R.string.search)) }; LazyColumn { items(results) { r -> TextButton({ onOpen(r.conversation_id) }) { Text("${r.conversation_title}: ${r.snippet}") } } } } }, confirmButton = { TextButton({ onOpen(-1) }) { Text(tr(language, R.string.close)) } })
}

@Composable
fun VoiceInputButton(language: String, onText: (String) -> Unit) {
    val context = LocalContext.current
    var available by remember { mutableStateOf(SpeechRecognizer.isRecognitionAvailable(context)) }
    val permissionLauncher = androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) startVoice(context, language, onText) }
    if (!available) return
    IconButton(onClick = {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startVoice(context, language, onText)
        else permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }) { Icon(Icons.Default.Mic, tr(language, R.string.voice_input)) }
}

private fun startVoice(context: Context, language: String, onText: (String) -> Unit) {
    val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
    recognizer.setRecognitionListener(object : android.speech.RecognitionListener {
        override fun onResults(results: Bundle) { results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let(onText); recognizer.destroy() }
        override fun onError(error: Int) { recognizer.destroy() }
        override fun onReadyForSpeech(p: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(r: Float) {}
        override fun onBufferReceived(b: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onPartialResults(b: Bundle?) {}
        override fun onEvent(t: Int,b: Bundle?) {}
    })
    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply { putExtra(RecognizerIntent.EXTRA_LANGUAGE, if (language == "ar") "ar" else "en-US"); putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM) }
    recognizer.startListening(intent)
}


private fun share(context: Context, text: String) { context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply { type = "text/plain"; putExtra(Intent.EXTRA_TEXT, text) }, "Rafiq AI")) }

@Composable
fun ProductWorkspace(app: RafiqApplication, api: RafiqApi, language: String, mod: Modifier) {
    val scope=rememberCoroutineScope(); val repository=remember(api){WorkspaceRepository(api)}; var section by remember { mutableStateOf("home") }; var notice by remember { mutableStateOf<String?>(null) }; val vm:WorkspaceViewModel = viewModel(key="workspace", factory=object:androidx.lifecycle.ViewModelProvider.Factory{override fun <T:androidx.lifecycle.ViewModel> create(modelClass:Class<T>):T=WorkspaceViewModel(repository) as T}); val state by vm.state.collectAsState(); val projects=state.projects; val artifacts=state.artifacts; val automations=state.automations; val files=state.files; val usage=state.usage
    LaunchedEffect(Unit){vm.refresh()}
    fun refresh(){vm.refresh()}
    if(section=="home") LazyColumn(mod.padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
        item{Text(if(language=="ar")"مساحة Rafiq AI":"Rafiq AI Workspace",style=MaterialTheme.typography.headlineSmall);Text(if(language=="ar")"كل قدرات المنتج أصبحت قابلة للوصول من الهاتف":"All product capabilities are accessible from mobile")}
        item{WorkspaceCard("Projects", "${projects.size} projects") { section="projects" }}
        item{WorkspaceCard("Deep Research", "Search • sources • citations • confidence") { section="research" }}
        item{WorkspaceCard("Agents", "Queue • progress • cancel • audit") { section="agents" }}
        item{WorkspaceCard("RAG", "Hybrid retrieval • citations • provider status") { section="rag" }}
        item{WorkspaceCard("Artifacts", "Documents • Markdown • Code • versions") { section="artifacts" }}
        item{WorkspaceCard("Automations", "Schedules • workers • execution state") { section="automations" }}
        item{WorkspaceCard("Files", "Upload • index • inspect") { section="files" }}
        item{WorkspaceCard("Usage / Billing", "${usage["plan"] ?: "free"} • ${usage["cost_usd"] ?: 0} USD / 30d") { section="usage" }}
        item{WorkspaceCard("Global Search", "Conversations • projects • files • memory") { section="search" }}
        item{WorkspaceCard("AI Registry / Safety / Eval", "Models • gateway • regression score") { section="quality" }}
    } else when(section){
        "projects"->ProjectScreen(repository,projects,files,language,{refresh()},{section="home"})
        "research"->ResearchScreen(repository,language,{section="home"})
        "agents"->AgentScreen(repository,language,{section="home"})
        "rag"->RagScreen(repository,projects,language,{section="home"})
        "artifacts"->ArtifactScreen(repository,artifacts,language,{refresh();section="home"})
        "automations"->AutomationScreen(repository,automations,language,{refresh();section="home"})
        "files"->FileScreen(repository,files,language,{refresh();section="home"})
        "usage"->UsageScreen(repository,usage,language,{section="home"})
        "search"->GlobalSearchScreen(repository,language,{section="home"})
        "quality"->QualityScreen(repository,language,{section="home"})
    }
    notice?.let{AlertDialog(onDismissRequest={notice=null},title={Text("Rafiq AI")},text={Text(it)},confirmButton={TextButton({notice=null}){Text("OK")}})}
}
@Composable private fun WorkspaceCard(title:String,subtitle:String,onClick:()->Unit){Card(Modifier.fillMaxWidth()){TextButton(onClick,Modifier.fillMaxWidth().padding(8.dp)){Column(Modifier.fillMaxWidth()){Text(title,style=MaterialTheme.typography.titleMedium);Text(subtitle,style=MaterialTheme.typography.bodySmall)}}}}
@Composable private fun BackTitle(title:String,back:()->Unit){Row(verticalAlignment=Alignment.CenterVertically){IconButton(back){Icon(Icons.Default.ArrowBack,null)};Text(title,style=MaterialTheme.typography.titleLarge)}}
@Composable private fun ProjectScreen(repository:WorkspaceRepository,projects:List<ProjectDto>,files:List<FileDto>,language:String,refresh:()->Unit,back:()->Unit){val scope=rememberCoroutineScope();var name by remember{mutableStateOf("")};var selected by remember{mutableStateOf<ProjectDto?>(null)};var ctx by remember{mutableStateOf<Map<String,Any?>>(emptyMap())};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Projects",back);Row{OutlinedTextField(name,{name=it},Modifier.weight(1f),placeholder={Text("New project")});Button(enabled=name.isNotBlank(),onClick={scope.launch{runCatching{repository.createProject(ProjectCreateBody(name.trim()))}.onSuccess{refresh();name=""}}}){Text("+")}};LazyColumn{items(projects){p->Card(Modifier.fillMaxWidth().padding(vertical=4.dp)){Column(Modifier.padding(10.dp)){Text(p.name);Text(p.instructions,style=MaterialTheme.typography.bodySmall);Row{Button({selected=p;scope.launch{runCatching{ctx=repository.projectContext(p.id)}}}){Text("Open")};Button({scope.launch{runCatching{repository.deleteProject(p.id);refresh()}}}){Text("Delete")}}}}};selected?.let{p->Text("Project context: ${ctx.keys.joinToString()}");Text("Files available: ${files.size}");Button({scope.launch{runCatching{repository.saveProjectMemory(p.id,"mobile_access","enabled")}}}){Text("Save project memory")}}}}}
@Composable private fun ResearchScreen(repository:WorkspaceRepository,language:String,back:()->Unit){val scope=rememberCoroutineScope();var q by remember{mutableStateOf("")};var r by remember{mutableStateOf<ResearchDto?>(null)};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Deep Research",back);OutlinedTextField(q,{q=it},Modifier.fillMaxWidth(),placeholder={Text("Research question")});Button(enabled=q.length>2,onClick={scope.launch{runCatching{repository.research(mapOf("query" to q,"limit" to 8))}.onSuccess{r=it}}}){Text("Start research")};r?.let{x->Text("Status: ${x.status}");Text("Sources: ${x.sources.size}");x.sources.forEach{Card(Modifier.fillMaxWidth().padding(4.dp)){Column(Modifier.padding(8.dp)){Text(it.title);Text(it.url,style=MaterialTheme.typography.labelSmall);Text("Quality: ${it.quality_score ?: 0}")}}};Text("Report: ${x.result["synthesis"] ?: x.result}")}}}
@Composable private fun AgentScreen(repository:WorkspaceRepository,language:String,back:()->Unit){val scope=rememberCoroutineScope();var goal by remember{mutableStateOf("")};var a by remember{mutableStateOf<AgentResponseDto?>(null)};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Agents",back);OutlinedTextField(goal,{goal=it},Modifier.fillMaxWidth(),placeholder={Text("Goal")});Button(enabled=goal.length>2,onClick={scope.launch{runCatching{repository.runAgent(AgentRequestBody(goal,approved_tools=listOf("search","fetch")))}.onSuccess{a=it}}}){Text("Run agent")};a?.let{x->Text("Run ${x.run_id}: ${x.status}");Text(x.result.toString());Button({scope.launch{runCatching{a=repository.getAgent(x.run_id)}}}){Text("Refresh progress")};Button({scope.launch{runCatching{a=repository.cancelAgent(x.run_id)}}}){Text("Cancel")}}}}
@Composable private fun RagScreen(repository:WorkspaceRepository,projects:List<ProjectDto>,language:String,back:()->Unit){val scope=rememberCoroutineScope();var q by remember{mutableStateOf("")};var p by remember{mutableStateOf<ProjectDto?>(null)};var result by remember{mutableStateOf<Map<String,Any?>>(emptyMap())};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("RAG",back);projects.forEach{Button({p=it},Modifier.fillMaxWidth()){Text("Project: ${it.name}")}};OutlinedTextField(q,{q=it},Modifier.fillMaxWidth(),placeholder={Text("Ask your project files")});Button(enabled=p!=null&&q.isNotBlank(),onClick={scope.launch{runCatching{result=repository.ragSearch(p!!.id,q)}}}){Text("Search")};Text(result.toString())}}
@Composable private fun ArtifactScreen(repository:WorkspaceRepository,items:List<ArtifactDto>,language:String,refresh:()->Unit,back:()->Unit){val scope=rememberCoroutineScope();var name by remember{mutableStateOf("")};var content by remember{mutableStateOf("")};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Artifacts",back);OutlinedTextField(name,{name=it},placeholder={Text("Name")});OutlinedTextField(content,{content=it},Modifier.fillMaxWidth(),minLines=5);Button(enabled=name.isNotBlank(),onClick={scope.launch{runCatching{repository.createArtifact(ArtifactCreateBody(name,"markdown",content))}.onSuccess{refresh();name="";content=""}}}){Text("Create")};LazyColumn{items(items){a->Card(Modifier.fillMaxWidth().padding(4.dp)){Column(Modifier.padding(8.dp)){Text("${a.name} v${a.version}");Text(a.content,maxLines=5)}}}}}}
@Composable private fun AutomationScreen(repository:WorkspaceRepository,items:List<AutomationDto>,language:String,refresh:()->Unit,back:()->Unit){val scope=rememberCoroutineScope();var name by remember{mutableStateOf("")};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Automations",back);OutlinedTextField(name,{name=it},placeholder={Text("Automation name")});Button(enabled=name.isNotBlank(),onClick={scope.launch{runCatching{repository.createSchedule(name)}.onSuccess{refresh();name=""}}}){Text("Create schedule")};items.forEach{Text("${it.name} • ${it.trigger_type} • ${it.last_run_at ?: "never"}")}}}
@Composable private fun FileScreen(repository:WorkspaceRepository,items:List<FileDto>,language:String,refresh:()->Unit,back:()->Unit){val context=LocalContext.current;val scope=rememberCoroutineScope();val launcher=androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->uri?.let{scope.launch{runCatching{context.contentResolver.openInputStream(it)?.use{stream->val bytes=stream.readBytes();val cursor=context.contentResolver.query(it,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null);val name=cursor?.use{c->if(c.moveToFirst())c.getString(0)else null} ?: "upload";val mime=context.contentResolver.getType(it) ?: "application/octet-stream";repository.uploadFile(okhttp3.MultipartBody.Part.createFormData("file",name,bytes.toRequestBody(mime.toMediaType())))}}.onSuccess{refresh()}}}};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Files",back);Button({launcher.launch(arrayOf("application/pdf","text/plain","text/csv","application/*","image/*"))}){Text("Upload file")};items.forEach{Text("${it.filename} • ${it.status}")}}}
@Composable private fun UsageScreen(repository:WorkspaceRepository,usage:Map<String,Any?>,language:String,back:()->Unit){Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Usage / Billing",back);Text(usage.toString());Text("Billing entitlement is enforced by Backend; Play purchase verification remains required for live store validation.")}}
@Composable private fun GlobalSearchScreen(repository:WorkspaceRepository,language:String,back:()->Unit){val scope=rememberCoroutineScope();var q by remember{mutableStateOf("")};var r by remember{mutableStateOf<Map<String,Any?>>(emptyMap())};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("Global Search",back);OutlinedTextField(q,{q=it},Modifier.fillMaxWidth());Button({scope.launch{runCatching{r=repository.globalSearch(q)}}}){Text("Search")};Text(r.toString())}}
@Composable private fun QualityScreen(repository:WorkspaceRepository,language:String,back:()->Unit){val scope=rememberCoroutineScope();var eval by remember{mutableStateOf<Map<String,Any?>>(emptyMap())};var models by remember{mutableStateOf<List<Map<String,Any?>>>(emptyList())};Column(Modifier.fillMaxSize().padding(16.dp)){BackTitle("AI Quality",back);Button({scope.launch{runCatching{eval=repository.evalStatus();models=repository.models()}}}){Text("Run / refresh evaluation")};Text("Eval: $eval");models.forEach{Text("${it["name"]} • ${it["provider"]} • quality ${it["quality"]} • speed ${it["speed"]}")}}}

package com.rafiqai.app.data.network

import com.rafiqai.app.SecureSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class StreamingClient(private val session: SecureSession) {
    private val client = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(0, TimeUnit.MILLISECONDS).authenticator(TokenAuthenticator(session)).addInterceptor(AuthInterceptor(session)).build()
    fun message(conversationId: Long, content: String): Flow<String> = flow {
        val json = JSONObject().put("content", content).toString()
        val request = Request.Builder().url(BuildConfig.BASE_URL + "conversations/$conversationId/messages/stream").post(json.toRequestBody("application/json".toMediaType())).build()
        withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}")
                val source = response.body?.source() ?: return@withContext
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue
                    val payload = line.removePrefix("data:").trim()
                    if (payload.isBlank()) continue
                    if (payload == "[DONE]") break
                    val obj = runCatching { JSONObject(payload) }.getOrNull() ?: continue
                    if (obj.optString("type") == "delta") emit(obj.optString("text"))
                    if (obj.optString("type") == "error") error("AI stream failed")
                }
            }
        }
    }
}

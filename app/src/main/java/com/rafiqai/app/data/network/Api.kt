package com.rafiqai.app.data.network

import retrofit2.Response
import retrofit2.http.*

data class AuthBody(val email: String, val password: String)
data class TokenResponse(val access_token: String, val refresh_token: String, val token_type: String)
data class RefreshBody(val refresh_token: String)
data class ProfileDto(val email: String, val display_name: String, val locale: String, val memory_enabled: Boolean = false, val analytics_enabled: Boolean = true, val plan: String = "free", val created_at: String)
data class ProfileUpdate(val display_name: String? = null, val locale: String = "ar", val memory_enabled: Boolean? = null, val analytics_enabled: Boolean? = null)
data class ConversationDto(val id: Long, val title: String, val pinned: Boolean = false, val updated_at: String)
data class MessageDto(val id: Long, val conversation_id: Long, val role: String, val content: String, val created_at: String)
data class TaskDto(val id: Long, val title: String, val description: String, val completed: Boolean, val due_at: String?, val priority: String = "normal", val recurrence: String? = null, val updated_at: String)
data class SearchResultDto(val conversation_id: Long, val conversation_title: String, val message_id: Long, val role: String, val snippet: String, val created_at: String)
data class SyncDto(val conversations: List<ConversationDto>, val tasks: List<TaskDto>, val messages: List<MessageDto>, val server_time: String)
data class ConversationCreate(val title: String = "محادثة جديدة")
data class ConversationUpdate(val title: String)
data class MessageCreate(val content: String)
data class TaskCreate(val title: String, val description: String = "", val due_at: String? = null, val priority: String = "normal", val recurrence: String? = null)
data class TaskUpdate(val title: String? = null, val description: String? = null, val completed: Boolean? = null, val due_at: String? = null, val priority: String? = null, val recurrence: String? = null)
data class Page<T>(val items: List<T>, val next_cursor: String?)

interface RafiqApi {
    @POST("auth/register") suspend fun register(@Body body: AuthBody): TokenResponse
    @POST("auth/login") suspend fun login(@Body body: AuthBody): TokenResponse
    @POST("auth/refresh") suspend fun refresh(@Body body: RefreshBody): TokenResponse
    @POST("auth/logout") suspend fun logout(@Body body: RefreshBody): Response<Unit>
    @DELETE("auth/me") suspend fun deleteAccount(): Response<Unit>
    @POST("auth/logout-all") suspend fun logoutAll(): Response<Unit>
    @GET("auth/sessions") suspend fun sessions(): List<Map<String, Any>>
    @PATCH("auth/password") suspend fun changePassword(@Body body: Map<String,String>): Response<Unit>
    @PATCH("auth/email") suspend fun changeEmail(@Body body: Map<String,String>): Response<Unit>
    @GET("me") suspend fun profile(): ProfileDto
    @PATCH("me") suspend fun updateProfile(@Body body: ProfileUpdate): ProfileDto
    @GET("conversations") suspend fun conversations(@Query("limit") limit: Int = 50, @Query("cursor") cursor: String? = null): Page<ConversationDto>
    @POST("conversations") suspend fun createConversation(@Body body: ConversationCreate): ConversationDto
    @PATCH("conversations/{id}") suspend fun renameConversation(@Path("id") id: Long, @Body body: ConversationUpdate): ConversationDto
    @DELETE("conversations/{id}") suspend fun deleteConversation(@Path("id") id: Long): Response<Unit>
    @GET("conversations/{id}/messages") suspend fun messages(@Path("id") id: Long, @Query("limit") limit: Int = 100, @Query("cursor") cursor: String? = null): Page<MessageDto>
    @POST("conversations/{id}/messages") suspend fun sendMessage(@Path("id") id: Long, @Body body: MessageCreate): MessageDto
    @DELETE("conversations/{cid}/messages/{mid}") suspend fun deleteMessage(@Path("cid") cid: Long, @Path("mid") mid: Long): Response<Unit>
    @GET("memories") suspend fun memories(): List<MemoryDto>
    @POST("memories") suspend fun createMemory(@Body body: MemoryBody): MemoryDto
    @PATCH("memories/{id}") suspend fun updateMemory(@Path("id") id: Long, @Body body: MemoryBody): MemoryDto
    @DELETE("memories/{id}") suspend fun deleteMemory(@Path("id") id: Long): Response<Unit>
    @PUT("memory/settings") suspend fun memorySettings(@Body body: MemorySettingsBody): Map<String,Boolean>
    @GET("search") suspend fun search(@Query("q") query: String): List<SearchResultDto>
    @GET("sync") suspend fun sync(@Query("since") since: String? = null): SyncDto
    @GET("tasks") suspend fun tasks(): List<TaskDto>
    @POST("tasks") suspend fun createTask(@Body body: TaskCreate): TaskDto
    @PATCH("tasks/{id}") suspend fun updateTask(@Path("id") id: Long, @Body body: TaskUpdate): TaskDto
    @DELETE("tasks/{id}") suspend fun deleteTask(@Path("id") id: Long): Response<Unit>
    @GET("billing/entitlement") suspend fun entitlement(): EntitlementDto
    @POST("billing/verify") suspend fun verifyPurchase(@Body body: PurchaseVerifyBody): EntitlementDto
    @POST("devices/fcm") suspend fun registerFcm(@Body body: DeviceTokenBody): Response<Unit>
    @GET("web-search") suspend fun webSearch(@Query("q") query: String): WebSearchDto
    @Multipart
    @POST("files") suspend fun uploadFile(@Part file: okhttp3.MultipartBody.Part, @Query("conversation_id") conversationId: Long? = null): FileDto
    @GET("files") suspend fun files(): List<FileDto>
    @DELETE("files/{id}") suspend fun deleteFile(@Path("id") id: Long): Response<Unit>
    @POST("analytics/events") suspend fun analytics(@Body body: Map<String,Any?>): Response<Unit>
    @GET("export") suspend fun exportData(): retrofit2.Response<okhttp3.ResponseBody>
    @GET("projects") suspend fun projects(): List<ProjectDto>
    @POST("projects") suspend fun createProject(@Body body: ProjectCreateBody): ProjectDto
    @PATCH("projects/{id}") suspend fun updateProject(@Path("id") id: Long, @Body body: ProjectUpdateBody): ProjectDto
    @DELETE("projects/{id}") suspend fun deleteProject(@Path("id") id: Long): Response<Unit>
    @POST("projects/{id}/conversations") suspend fun linkProjectConversation(@Path("id") id: Long, @Body body: Map<String,Any?>): Map<String,Any?>
    @GET("projects/{id}/context") suspend fun projectContext(@Path("id") id: Long): Map<String,Any?>
    @POST("projects/{id}/memory") suspend fun projectMemory(@Path("id") id: Long, @Body body: Map<String,Any?>): Map<String,Any?>
    @POST("projects/{id}/files/{fid}/index") suspend fun indexProjectFile(@Path("id") id: Long,@Path("fid") fid: Long): Map<String,Any?>
    @GET("projects/{id}/rag-search") suspend fun ragSearch(@Path("id") id: Long,@Query("q") q: String): Map<String,Any?>
    @POST("agents/run") suspend fun runAgent(@Body body: AgentRequestBody): AgentResponseDto
    @GET("agents/{id}") suspend fun getAgent(@Path("id") id: String): AgentResponseDto
    @POST("agents/{id}/cancel") suspend fun cancelAgent(@Path("id") id: String): Map<String,Any?>
    @POST("research") suspend fun research(@Body body: Map<String,Any?>): ResearchDto
    @GET("research/{id}") suspend fun research(@Path("id") id: String): ResearchDto
    @GET("artifacts") suspend fun artifacts(): List<ArtifactDto>
    @POST("artifacts") suspend fun createArtifact(@Body body: ArtifactCreateBody): ArtifactDto
    @PATCH("artifacts/{id}") suspend fun updateArtifact(@Path("id") id: Long, @Body body: ArtifactUpdateBody): ArtifactDto
    @DELETE("artifacts/{id}") suspend fun deleteArtifact(@Path("id") id: Long): Response<Unit>
    @GET("automations") suspend fun automations(): List<AutomationDto>
    @POST("automations") suspend fun createAutomation(@Body body: Map<String,Any?>): AutomationDto
    @DELETE("automations/{id}") suspend fun deleteAutomation(@Path("id") id: Long): Response<Unit>
    @GET("ai/models") suspend fun models(): List<Map<String,Any?>>
    @GET("ai/safety") suspend fun safety(): Map<String,Any?>
    @GET("eval/status") suspend fun evalStatus(): Map<String,Any?>
    @GET("search/global") suspend fun globalSearch(@Query("q") query: String): Map<String,Any?>
    @GET("usage/me") suspend fun usage(): Map<String,Any?>
}


data class MemoryDto(val id: Long, val key: String, val value: String, val category: String, val sensitive: Boolean, val created_at: String, val updated_at: String)
data class MemoryBody(val key: String, val value: String, val category: String = "preference", val sensitive: Boolean = false)
data class MemorySettingsBody(val enabled: Boolean)
data class EntitlementDto(val plan: String, val active: Boolean, val expires_at: String?, val product_id: String?)
data class PurchaseVerifyBody(val product_id: String, val purchase_token: String)
data class DeviceTokenBody(val token: String, val platform: String = "android")
data class FileDto(val id: Long, val filename: String, val content_type: String, val size_bytes: Long, val status: String, val created_at: String, val download_url: String?)
data class WebSearchResultDto(val title: String, val url: String, val snippet: String)
data class WebSearchDto(val query: String, val results: List<WebSearchResultDto>)

data class ProjectDto(val id: Long, val name: String, val instructions: String, val created_at: String, val updated_at: String)
data class ProjectCreateBody(val name: String, val instructions: String = "")
data class ProjectUpdateBody(val name: String? = null, val instructions: String? = null)
data class AgentRequestBody(val goal: String, val task_type: String = "agent", val model_preference: String = "balanced", val approved_tools: List<String> = emptyList())
data class AgentResponseDto(val run_id: String, val status: String, val plan: List<Map<String,Any?>>, val result: Map<String,Any?>)
data class ResearchSourceDto(val url: String, val title: String, val snippet: String, val quality_score: Double? = null, val source_id: String? = null)
data class ResearchDto(val id: String, val query: String, val status: String, val sources: List<ResearchSourceDto>, val result: Map<String,Any?>)
data class ArtifactDto(val id: Long, val name: String, val kind: String, val content: String, val version: Int, val project_id: Long?, val updated_at: String)
data class ArtifactCreateBody(val name: String, val kind: String, val content: String = "", val project_id: Long? = null)
data class ArtifactUpdateBody(val content: String, val name: String? = null)
data class AutomationDto(val id: Long, val name: String, val trigger_type: String, val trigger: Map<String,Any?>, val action: Map<String,Any?>, val enabled: Boolean, val last_run_at: String?)

package com.rafiqai.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rafiqai.app.data.network.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class WorkspaceState(val loading:Boolean=false,val projects:List<ProjectDto> = emptyList(),val artifacts:List<ArtifactDto> = emptyList(),val automations:List<AutomationDto> = emptyList(),val files:List<FileDto> = emptyList(),val usage:Map<String,Any?> = emptyMap(),val error:String?=null)

class WorkspaceRepository(private val api:RafiqApi) {
    suspend fun load()=WorkspaceState(projects=api.projects(),artifacts=api.artifacts(),automations=api.automations(),files=api.files(),usage=api.usage())
    suspend fun createProject(name:String)=api.createProject(ProjectCreateBody(name))
    suspend fun deleteProject(id:Long)=api.deleteProject(id)
    suspend fun projectContext(id:Long)=api.projectContext(id)
    suspend fun saveProjectMemory(id:Long,key:String,value:String)=api.projectMemory(id,mapOf("key" to key,"value" to value))
    suspend fun ragSearch(id:Long,q:String)=api.ragSearch(id,q)
    suspend fun runAgent(body:AgentRequestBody)=api.runAgent(body)
    suspend fun getAgent(id:String)=api.getAgent(id)
    suspend fun cancelAgent(id:String)=api.cancelAgent(id)
    suspend fun research(body:Map<String,Any?>)=api.research(body)
    suspend fun getResearch(id:String)=api.research(id)
    suspend fun createArtifact(body:ArtifactCreateBody)=api.createArtifact(body)
    suspend fun createSchedule(name:String)=api.createAutomation(mapOf("name" to name,"trigger_type" to "schedule","trigger" to mapOf("interval_minutes" to 60),"action" to mapOf("type" to "research","query" to name,"limit" to 8),"enabled" to true))
    suspend fun deleteAutomation(id:Long)=api.deleteAutomation(id)
    suspend fun uploadFile(part:okhttp3.MultipartBody.Part)=api.uploadFile(part)
    suspend fun globalSearch(q:String)=api.globalSearch(q)
    suspend fun usage()=api.usage()
    suspend fun models()=api.models()
    suspend fun safety()=api.safety()
    suspend fun evalStatus()=api.evalStatus()
}

class WorkspaceViewModel(private val repository:WorkspaceRepository):ViewModel(){
    private val _state=MutableStateFlow(WorkspaceState(loading=true)); val state:StateFlow<WorkspaceState> = _state.asStateFlow()
    fun refresh(){viewModelScope.launch{_state.value=_state.value.copy(loading=true,error=null);runCatching{repository.load()}.onSuccess{_state.value=it.copy(loading=false)}.onFailure{_state.value=_state.value.copy(loading=false,error=it.message)}}}
    fun createProject(name:String){viewModelScope.launch{runCatching{repository.createProject(name)}.onSuccess{refresh()}.onFailure{_state.value=_state.value.copy(error=it.message)}}}
    fun createArtifact(name:String,content:String){viewModelScope.launch{runCatching{repository.createArtifact(ArtifactCreateBody(name,"markdown",content))}.onSuccess{refresh()}.onFailure{_state.value=_state.value.copy(error=it.message)}}}
    fun createSchedule(name:String){viewModelScope.launch{runCatching{repository.createSchedule(name)}.onSuccess{refresh()}.onFailure{_state.value=_state.value.copy(error=it.message)}}}
}

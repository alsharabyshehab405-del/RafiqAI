package com.rafiqai.app.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "conversations", indices = [Index("updatedAt")])
data class ConversationEntity(@PrimaryKey val id: Long, val title: String, val updatedAt: Long, val synced: Boolean = true)

@Entity(tableName = "messages", indices = [Index("conversationId"), Index("createdAt")])
data class MessageEntity(@PrimaryKey val id: Long, val conversationId: Long, val role: String, val content: String, val createdAt: Long, val synced: Boolean = true)

@Entity(tableName = "tasks", indices = [Index("updatedAt")])
data class TaskEntity(@PrimaryKey val id: Long, val title: String, val description: String, val completed: Boolean, val dueAt: Long?, val priority: String = "normal", val recurrence: String? = null, val updatedAt: Long, val synced: Boolean = true)

@Dao interface ConversationDao {
    @Query("SELECT * FROM conversations ORDER BY updatedAt DESC") fun observe(): Flow<List<ConversationEntity>>
    @Query("SELECT * FROM conversations WHERE id = :id") suspend fun get(id: Long): ConversationEntity?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(item: ConversationEntity)
    @Query("DELETE FROM conversations WHERE id = :id") suspend fun delete(id: Long)
    @Query("DELETE FROM conversations") suspend fun clear()
}

@Dao interface MessageDao {
    @Query("SELECT * FROM messages WHERE conversationId = :conversationId ORDER BY createdAt ASC LIMIT :limit OFFSET :offset") suspend fun page(conversationId: Long, limit: Int, offset: Int): List<MessageEntity>
    @Query("SELECT * FROM messages WHERE content LIKE '%' || :query || '%' ORDER BY createdAt DESC LIMIT 50") suspend fun search(query: String): List<MessageEntity>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(item: MessageEntity)
    @Query("DELETE FROM messages WHERE id = :id") suspend fun delete(id: Long)
    @Query("DELETE FROM messages WHERE conversationId = :conversationId") suspend fun deleteForConversation(conversationId: Long)
}

@Dao interface TaskDao {
    @Query("SELECT * FROM tasks ORDER BY updatedAt DESC") fun observe(): Flow<List<TaskEntity>>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(item: TaskEntity)
    @Query("DELETE FROM tasks WHERE id = :id") suspend fun delete(id: Long)
}

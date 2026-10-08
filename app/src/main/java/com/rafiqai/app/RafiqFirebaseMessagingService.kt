package com.rafiqai.app

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.rafiqai.app.data.network.ApiClientFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class RafiqFirebaseMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        val app = application as RafiqApplication
        CoroutineScope(Dispatchers.IO).launch {
            runCatching { ApiClientFactory.create(app.session).registerFcm(com.rafiqai.app.data.network.DeviceTokenBody(token)) }
        }
    }
    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val title = message.notification?.title ?: message.data["title"] ?: "Rafiq AI"
        val body = message.notification?.body ?: message.data["body"] ?: ""
        RafiqNotifications.show(this, title, body)
    }
}

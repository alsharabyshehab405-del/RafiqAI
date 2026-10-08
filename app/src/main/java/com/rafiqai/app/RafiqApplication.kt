package com.rafiqai.app

import android.app.Application
import androidx.room.Room
import com.rafiqai.app.data.local.RafiqDatabase
import io.sentry.android.core.SentryAndroid
import com.google.firebase.FirebaseApp
import com.google.firebase.crashlytics.FirebaseCrashlytics

class RafiqApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.SENTRY_DSN.isNotBlank()) SentryAndroid.init(this) { options -> options.dsn = BuildConfig.SENTRY_DSN; options.isSendDefaultPii = false; options.environment = "production" }
        runCatching {
            if (FirebaseApp.initializeApp(this) != null) FirebaseCrashlytics.getInstance().setCrashlyticsCollectionEnabled(true)
        }
    }
    val database by lazy { Room.databaseBuilder(this, RafiqDatabase::class.java, "rafiq.db").addMigrations(RafiqDatabase.MIGRATION_1_2, RafiqDatabase.MIGRATION_2_3).fallbackToDestructiveMigrationOnDowngrade().build() }
    val session by lazy { SecureSession(this) }
    val preferences by lazy { AppPreferences(this) }
}

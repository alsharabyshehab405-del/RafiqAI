package com.rafiqai.app

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.datastore.preferences.core.edit
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.rafiqPrefs by preferencesDataStore("rafiq_preferences")
class AppPreferences(private val context: Context) {
    private val darkKey = booleanPreferencesKey("dark_mode")
    private val languageKey = stringPreferencesKey("language")
    private val onboardingKey = booleanPreferencesKey("onboarding_done")
    val dark: Flow<Boolean> = context.rafiqPrefs.data.map { it[darkKey] ?: false }
    val language: Flow<String> = context.rafiqPrefs.data.map { it[languageKey] ?: "ar" }
    val onboardingDone: Flow<Boolean> = context.rafiqPrefs.data.map { it[onboardingKey] ?: false }
    suspend fun setDark(value: Boolean) { context.rafiqPrefs.edit { it[darkKey] = value } }
    suspend fun setLanguage(value: String) { context.rafiqPrefs.edit { it[languageKey] = value } }
    suspend fun setOnboardingDone(value: Boolean) { context.rafiqPrefs.edit { it[onboardingKey] = value } }
}

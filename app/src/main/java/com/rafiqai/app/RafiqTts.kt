package com.rafiqai.app

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

object RafiqTts : TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = null
    private var ready = false
    override fun onInit(status: Int) { ready = status == TextToSpeech.SUCCESS }
    private fun ensure(context: Context) { if (tts == null) tts = TextToSpeech(context.applicationContext, this) }
    fun speak(context: Context, text: String, locale: Locale = Locale.getDefault()) { ensure(context); tts?.language = locale; if (ready) tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "rafiq-${System.currentTimeMillis()}") }
    fun stop() { tts?.stop() }
    fun shutdown() { tts?.stop(); tts?.shutdown(); tts = null; ready = false }
}

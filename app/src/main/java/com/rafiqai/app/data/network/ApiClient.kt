package com.rafiqai.app.data.network

import com.rafiqai.app.BuildConfig
import com.rafiqai.app.SecureSession
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Route
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.random.Random

class TokenAuthenticator(private val session: SecureSession) : Authenticator {
    private val lock = Any()
    override fun authenticate(route: Route?, response: okhttp3.Response): Request? {
        if (responseCount(response) >= 2) return null
        val failedToken = response.request.header("Authorization")
        synchronized(lock) {
            val current = session.access()
            if (!failedToken.isNullOrBlank() && current != null && failedToken != "Bearer $current") {
                return response.request.newBuilder().header("Authorization", "Bearer $current").build()
            }
            val refresh = session.refresh() ?: return null
            val api = Retrofit.Builder().baseUrl(BuildConfig.BASE_URL).client(OkHttpClient()).addConverterFactory(GsonConverterFactory.create()).build().create(RafiqApi::class.java)
            val refreshed = runBlocking { runCatching { api.refresh(RefreshBody(refresh)) }.getOrNull() } ?: return null
            session.save(refreshed.access_token, refreshed.refresh_token)
            return response.request.newBuilder().header("Authorization", "Bearer ${refreshed.access_token}").build()
        }
    }
    private fun responseCount(r: okhttp3.Response): Int { var n = 1; var p = r.priorResponse; while (p != null) { n++; p = p.priorResponse }; return n }
}

class RetryInterceptor : okhttp3.Interceptor {
    override fun intercept(chain: okhttp3.Interceptor.Chain): okhttp3.Response {
        val request = chain.request()
        val retryableMethod = request.method in setOf("GET", "HEAD", "PUT", "DELETE") || request.header("Idempotency-Key") != null
        if (!retryableMethod) return chain.proceed(request)
        var last: IOException? = null
        repeat(3) { attempt ->
            try {
                val response = chain.proceed(request)
                if (response.code !in setOf(502,503,504) || attempt == 2) return response
                response.close()
                Thread.sleep((250L shl attempt) + Random.nextLong(0,150))
            } catch (e: IOException) {
                last=e
                if (attempt < 2) Thread.sleep((250L shl attempt) + Random.nextLong(0,150))
            }
        }
        throw last ?: IOException("network error")
    }
}

class AuthInterceptor(private val session: SecureSession) : okhttp3.Interceptor {
    override fun intercept(chain: okhttp3.Interceptor.Chain): okhttp3.Response {
        val token = session.access() ?: return chain.proceed(chain.request())
        return chain.proceed(chain.request().newBuilder().header("Authorization", "Bearer $token").header("Accept", "application/json").build())
    }
}

object ApiClientFactory {
    fun create(session: SecureSession): RafiqApi {
        val client = OkHttpClient.Builder().addInterceptor(RetryInterceptor()).addInterceptor(AuthInterceptor(session)).authenticator(TokenAuthenticator(session)).connectTimeout(15, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).writeTimeout(60, TimeUnit.SECONDS).build()
        return Retrofit.Builder().baseUrl(BuildConfig.BASE_URL).client(client).addConverterFactory(GsonConverterFactory.create()).build().create(RafiqApi::class.java)
    }
}

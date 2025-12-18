// File: data/repository/RepositoryProvider.kt
package com.example.spcsingle.data.repository

import android.app.Application
import com.example.spcsingle.BuildConfig
import com.example.spcsingle.data.datasource.LocalRepository
import com.example.spcsingle.data.datasource.ServerRepository
import com.example.spcsingle.data.datasource.FirebaseRepository

object RepositoryProvider {

    fun provide(app: Application): DashboardRepository {
        return when (BuildConfig.DATA_SOURCE) {
            "LOCAL" -> LocalRepository(context = app)
            "SERVER" -> ServerRepository()
            "FIREBASE" -> FirebaseRepository()
            else -> error("Unknown DATA_SOURCE = ${BuildConfig.DATA_SOURCE}")
        }
    }
}

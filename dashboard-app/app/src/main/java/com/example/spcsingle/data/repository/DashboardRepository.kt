package com.example.spcsingle.data.repository

import com.example.spcsingle.DashboardUiState
import kotlinx.coroutines.flow.Flow
interface DashboardRepository {
    fun observeDashboard(
        sku: String
    ): Flow<DashboardUiState>
    suspend fun refreshDashboard(sku: String)
    suspend fun applyCorrection(sku: String)
    suspend fun fetchCurrentSku(): String?
}
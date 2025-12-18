package com.example.spcsingle.data.datasource

import android.content.Context
import com.example.spcsingle.*
import com.example.spcsingle.data.repository.DashboardRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine

class LocalRepository(
    context: Context
) : DashboardRepository {

    private val db = AppDatabase.getInstance(context)

    override fun observeDashboard(sku: String): Flow<DashboardUiState> {
        return combine(
            db.cycleDao().getRecentCycles(sku, 30),
            db.spcStateDao().getLatestState(sku),
            db.alarmDao().getRecentAlarms(sku, 20)
        ) { cycles, spc, alarms ->
            DashboardUiState(
                cycles = cycles,
                spcState = spc,
                alarms = alarms,
                currentSku = sku
            )
        }
    }

    override suspend fun refreshDashboard(sku: String) {
        // 1단계: 서버 없음 → 아무것도 안 함
    }

    override suspend fun applyCorrection(sku: String) {
        // 1단계: 서버 없음
    }
}

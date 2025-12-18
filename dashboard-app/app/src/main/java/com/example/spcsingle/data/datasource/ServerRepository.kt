// File: app/src/main/java/com/example/spcsingle/data/datasource/ServerRepository.kt
package com.example.spcsingle.data.datasource

import com.example.spcsingle.*
import com.example.spcsingle.data.repository.DashboardRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow

/**
 * SERVER 데이터소스
 *
 * 역할:
 * - MQTT는 백엔드에서 처리
 * - 앱은 REST API만 주기적으로 polling
 * - RFID / 알람 / 사이클 변화가 서버 DB에 반영되면
 *   앱은 3초 이내에 자동 갱신됨
 */
class ServerRepository(
    private val api: SpcApi = SpcApi.create()
) : DashboardRepository {

    override fun observeDashboard(sku: String): Flow<DashboardUiState> = flow {

        // 앱이 살아있는 동안 계속 polling
        while (true) {
            try {
                // 1️⃣ 최근 사이클 (캔 로그)
                val cycles = api.getRecentCycles(
                    sku = sku,
                    limit = 30
                ).map { it.toEntity() }

                // 2️⃣ 현재 SPC 상태
                val spcState = api.getSpcCurrent(sku)
                    .toEntity(sku)

                // 3️⃣ 최근 알람
                val alarms = api.getAlarms(
                    sku = sku,
                    limit = 20
                ).map { it.toEntity() }

                // 4️⃣ UI 상태 방출
                emit(
                    DashboardUiState(
                        cycles = cycles,
                        spcState = spcState,
                        alarms = alarms,
                        currentSku = sku
                    )
                )
            } catch (e: Exception) {
                // 서버/네트워크 오류 시 앱 크래시 방지
                emit(
                    DashboardUiState(
                        error = e.message ?: "Server error",
                        currentSku = sku
                    )
                )
            }

            // ⏱ 3초마다 서버 재조회
            delay(3_000)
        }
    }

    /**
     * 서버는 항상 최신 상태이므로 refresh는 noop
     */
    override suspend fun refreshDashboard(sku: String) {
        // no-op
    }

    /**
     * 자동 보정 요청 (UNO / Arduino 연동)
     */
    override suspend fun applyCorrection(sku: String) {
        api.applyCorrection(
            CorrectionRequest(sku_id = sku)
        )
    }
}

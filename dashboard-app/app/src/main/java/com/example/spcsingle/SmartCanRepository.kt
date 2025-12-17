package com.example.spcsingle

import kotlinx.coroutines.flow.Flow

class SmartCanRepository(
    private val api: SpcApi,
    private val db: AppDatabase,
) {

    fun observeCycles(sku: String, limit: Int): Flow<List<CycleEntity>> =
        db.cycleDao().getRecentCycles(sku, limit)

    fun observeSpcState(sku: String): Flow<SpcStateEntity?> =
        db.spcStateDao().getLatestState(sku)

    fun observeAlarms(sku: String, limit: Int): Flow<List<AlarmEntity>> =
        db.alarmDao().getRecentAlarms(sku, limit)

    suspend fun refreshDashboard(sku: String) {
        // 1) 서버에서 데이터 가져오기
        val cyclesDto = api.getRecentCycles(sku, limit = 30)
        val spcDto = api.getSpcCurrent(sku)
        val alarmsDto = api.getAlarms(sku, limit = 20)

        // 2) Room DB에 저장
        db.cycleDao().insertAll(cyclesDto.map { it.toEntity() })
        db.spcStateDao().insert(spcDto.toEntity(sku))
        db.alarmDao().insertAll(alarmsDto.map { it.toEntity() })
    }
}

package com.example.spcsingle.data.datasource

import com.example.spcsingle.*
import com.example.spcsingle.data.repository.DashboardRepository
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

class FirebaseRepository : DashboardRepository {

    private val db = FirebaseFirestore.getInstance()

    override fun observeDashboard(sku: String): Flow<DashboardUiState> = callbackFlow {

        val cyclesRef = db.collection("cycles")
            .whereEqualTo("sku", sku)
            .orderBy("created_at")
            .limit(30)

        val spcRef = db.collection("spc_states")
            .whereEqualTo("sku", sku)
            .orderBy("created_at")
            .limit(1)

        val alarmsRef = db.collection("alarms")
            .whereEqualTo("sku", sku)
            .orderBy("created_at")
            .limit(20)

        val cycles = cyclesRef.get().await().toObjects(CycleEntity::class.java)
        val spc = spcRef.get().await().toObjects(SpcStateEntity::class.java).firstOrNull()
        val alarms = alarmsRef.get().await().toObjects(AlarmEntity::class.java)

        trySend(
            DashboardUiState(
                cycles = cycles,
                spcState = spc,
                alarms = alarms,
                currentSku = sku
            )
        )

        close()
    }

    override suspend fun refreshDashboard(sku: String) {
        // Firestore는 pull 방식 → noop
    }

    override suspend fun applyCorrection(sku: String) {
        // 서버 연동 시 여기서 API 호출
    }
}

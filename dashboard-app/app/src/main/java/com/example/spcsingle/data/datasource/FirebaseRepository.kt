// FirebaseRepository.kt
package com.example.spcsingle.data.datasource

import com.example.spcsingle.*
import com.example.spcsingle.data.repository.DashboardRepository
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.tasks.await

class FirebaseRepository : DashboardRepository {

    private val firestore = FirebaseFirestore.getInstance()

    override fun observeDashboard(sku: String): Flow<DashboardUiState> = flow {
        while (true) {
            try {
                // 1️⃣ cycles
                val cyclesSnap = firestore.collection("cycles")
                    .whereEqualTo("sku", sku)
                    .orderBy("createdAt")
                    .limitToLast(30)
                    .get()
                    .await()

                val cycles = cyclesSnap.documents.mapNotNull { doc ->
                    runCatching {
                        CycleEntity(
                            id = doc.id.hashCode().toLong(),
                            sku = doc.getString("sku") ?: return@runCatching null,
                            seq = doc.getLong("seq")?.toInt() ?: 0,
                            targetMl = doc.getDouble("targetMl") ?: 0.0,
                            actualMl = doc.getDouble("actualMl"),
                            valveMs = doc.getLong("valveMs")?.toInt(),
                            error = doc.getDouble("error"),
                            spcState = doc.getString("spcState"),
                            createdAt = doc.getString("createdAt") ?: ""
                        )
                    }.getOrNull()
                }

                // 2️⃣ spc_state (현재 상태)
                val spcDoc = firestore.collection("spc_states")
                    .document(sku)
                    .get()
                    .await()

                val spcState = if (spcDoc.exists()) {
                    SpcStateEntity(
                        sku = sku,
                        spcState = spcDoc.getString("spcState") ?: "UNKNOWN",
                        alarmType = spcDoc.getString("alarmType"),
                        mean = spcDoc.getDouble("mean"),
                        std = spcDoc.getDouble("std"),
                        cusumPos = spcDoc.getDouble("cusumPos"),
                        cusumNeg = spcDoc.getDouble("cusumNeg"),
                        nSamples = spcDoc.getLong("nSamples")?.toInt(),
                        createdAt = spcDoc.getString("createdAt") ?: ""
                    )
                } else null

                // 3️⃣ alarms
                val alarmSnap = firestore.collection("alarms")
                    .whereEqualTo("sku", sku)
                    .orderBy("createdAt")
                    .limitToLast(20)
                    .get()
                    .await()

                val alarms = alarmSnap.documents.mapNotNull { doc ->
                    runCatching {
                        AlarmEntity(
                            id = doc.id.hashCode().toLong(),
                            sku = doc.getString("sku") ?: return@runCatching null,
                            level = doc.getString("level") ?: "INFO",
                            alarmType = doc.getString("alarmType"),
                            message = doc.getString("message"),
                            cycleId = null,
                            spcStateId = null,
                            createdAt = doc.getString("createdAt") ?: ""
                        )
                    }.getOrNull()
                }

                emit(
                    DashboardUiState(
                        cycles = cycles,
                        spcState = spcState,
                        alarms = alarms,
                        currentSku = sku
                    )
                )
            } catch (e: Exception) {
                emit(
                    DashboardUiState(
                        error = e.message ?: "Firebase error",
                        currentSku = sku
                    )
                )
            }

            delay(2_000) // Firebase polling (발표용)
        }
    }

    override suspend fun refreshDashboard(sku: String) {
        // Firebase는 실시간 DB → 명시적 refresh 필요 없음
    }

    override suspend fun applyCorrection(sku: String) {
        firestore.collection("spc_states")
            .document(sku)
            .update("spcState", "CORRECTED")
            .await()
    }

    override suspend fun fetchCurrentSku(): String? =
        "COKE_355"
}

package com.example.spcsingle
import kotlin.math.roundToInt
// /quality/spc_state 응답
data class SpcCurrentDto(
    val spc_state: String,
    val alarm_type: String?,
    val mean: Double?,
    val std: Double?,
    val cusum_pos: Double,
    val cusum_neg: Double,
    val n_samples: Int
)

// /quality/spc_states 응답 1건
data class SpcStateDto(
    val id: Long,
    val sku: String,
    val spc_state: String,
    val alarm_type: String?,
    val mean: Double?,
    val std: Double?,
    val cusum_pos: Double?,
    val cusum_neg: Double?,
    val n_samples: Int?,
    val last_cycle_id: Long?,
    val created_at: String,
)

// /quality/alarms 응답 1건
data class AlarmDto(
    val id: Long,
    val sku: String,
    val level: String,
    val alarm_type: String?,
    val message: String?,
    val cycle_id: Long?,
    val spc_state_id: Long?,
    val created_at: String,
)

// /cycles 관련 응답 1건 (백엔드 Cycle 스키마에 맞게 이름 맞춰야 함)
data class CycleDto(
    val id: Long,
    val sku: String,
    val seq: Int,
    val target_ml: Double,
    val actual_ml: Double?,
    val valve_ms: Double?,
    val error: Double?,
    val spc_state: String?,
    val created_at: String,
)
// QualityDtos.kt 맨 아래에 추가

fun CycleDto.toEntity(): CycleEntity =
    CycleEntity(
        id = id,
        sku = sku,
        seq = seq,
        targetMl = target_ml,
        actualMl = actual_ml,
        valveMs = valve_ms?.roundToInt(),
        error = error,
        spcState = spc_state,
        createdAt = created_at,
    )

fun SpcCurrentDto.toEntity(sku: String): SpcStateEntity =
    SpcStateEntity(
        sku = sku,
        spcState = spc_state,
        alarmType = alarm_type,
        mean = mean,
        std = std,
        cusumPos = cusum_pos,
        cusumNeg = cusum_neg,
        nSamples = n_samples,
        createdAt = "",    // 단순 현재 상태이므로 created_at이 따로 없다면 빈 값으로
    )

fun AlarmDto.toEntity(): AlarmEntity =
    AlarmEntity(
        id = id,
        sku = sku,
        level = level,
        alarmType = alarm_type,
        message = message,
        cycleId = cycle_id,
        spcStateId = spc_state_id,
        createdAt = created_at,
    )

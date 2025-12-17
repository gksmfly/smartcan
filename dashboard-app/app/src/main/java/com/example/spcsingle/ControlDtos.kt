package com.example.spcsingle

// === 센서 시뮬레이터 / 제어용 DTO ===

data class RunCycleRequest(
    val sku_id: String,
    val target_ml: Double?,
    val mode: String = "NORMAL",
)

data class RunCycleResponse(
    val sku_id: String,
    val cycle_no: Int,
    val target_amount: Double,
    val predicted_next_amount: Double,
    val valve_ms: Double,
    val status: String,
)

data class CurrentSkuDto(
    val sku_id: String?,
)

// 🔵 자동 오차 보정 요청/응답 DTO
data class CorrectionRequest(
    val sku_id: String,
)

data class CorrectionResponse(
    val status: String,   // 예: "CORRECTION_APPLIED"
)

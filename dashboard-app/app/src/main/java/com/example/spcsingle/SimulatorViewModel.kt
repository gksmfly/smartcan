package com.example.spcsingle

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SimulatorUiState(
    val isRunning: Boolean = false,      // 요청 진행 중 여부
    val lastStatus: String? = null,      // 마지막 요청 결과 상태 ("REQUESTED" 등)
    val errorMessage: String? = null,    // 에러 메시지
    val logs: List<String> = emptyList() // 로그 메시지 리스트
)

class SimulatorViewModel(
    private val api: SpcApi = SpcApi.create(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(SimulatorUiState())
    val uiState: StateFlow<SimulatorUiState> = _uiState

    private fun appendLog(msg: String) {
        _uiState.update { it.copy(logs = it.logs + msg) }
    }

    /**
     * 센서 시뮬레이터에서 사이클 실행
     *
     * @param sku     현재 선택된 SKU (COKE_355, CIDER_355 등)
     * @param targetMl 사용자가 입력한 target_ml (옵션, 없으면 null)
     */
    fun runCycle(sku: String, targetMl: Double?) {
        if (sku.isBlank()) {
            appendLog("⚠ SKU 비어있음")
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isRunning = true, errorMessage = null) }
            appendLog("➡ 요청: sku=$sku, target=$targetMl")

            try {
                val res = api.runCycle(
                    RunCycleRequest(
                        sku_id = sku,
                        target_ml = targetMl,
                        // mode 는 기본값 "NORMAL" 사용
                        // 필요하면 여기서 "NEG_DRIFT" 등으로 바꿔서 시나리오 분기 가능
                    )
                )
                appendLog("✅ 응답: status=${res.status}, valve_ms=${res.valve_ms}")
                _uiState.update {
                    it.copy(
                        isRunning = false,
                        lastStatus = res.status
                    )
                }
            } catch (e: Exception) {
                appendLog("❌ 오류: ${e.message}")
                _uiState.update {
                    it.copy(
                        isRunning = false,
                        errorMessage = e.message
                    )
                }
            }
        }
    }

    fun clearLogs() {
        _uiState.update { it.copy(logs = emptyList()) }
    }
}

package com.example.spcsingle

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch

data class DashboardUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val spcState: SpcStateEntity? = null,
    val alarms: List<AlarmEntity> = emptyList(),
    val cycles: List<CycleEntity> = emptyList(),
    val currentSku: String = "COKE_355",
)

@OptIn(ExperimentalCoroutinesApi::class)
class SpcViewModel(
    application: Application,
) : AndroidViewModel(application) {

    private val api = SpcApi.create()
    private val db = AppDatabase.getInstance(application)
    private val repo = SmartCanRepository(api, db)

    private val _sku = MutableStateFlow("COKE_355")
    val sku: StateFlow<String> = _sku.asStateFlow()

    private val _uiState = MutableStateFlow(
        DashboardUiState(currentSku = "COKE_355")
    )
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        // 1) Room Flow → UI 바인딩
        viewModelScope.launch {
            sku
                .flatMapLatest { currentSku ->
                    combine(
                        repo.observeCycles(currentSku, limit = 30),
                        repo.observeSpcState(currentSku),
                        repo.observeAlarms(currentSku, limit = 20),
                    ) { cycles, spc, alarms ->
                        _uiState.value.copy(
                            cycles = cycles,
                            spcState = spc,
                            alarms = alarms,
                            currentSku = currentSku,
                        )
                    }
                }
                .collect { newState ->
                    _uiState.value = newState
                }
        }

        // 2) 서버 폴링 – SKU별로 2초마다 refresh
        viewModelScope.launch {
            sku.collectLatest { currentSku ->
                while (true) {
                    refreshOnce(currentSku)
                    delay(2000L)
                }
            }
        }
    }

    fun setSku(newSku: String) {
        _sku.value = newSku
    }

    fun refresh() {
        val currentSku = _sku.value
        viewModelScope.launch {
            refreshOnce(currentSku)
        }
    }

    private suspend fun refreshOnce(currentSku: String) {
        _uiState.update { it.copy(isLoading = true, error = null) }
        try {
            repo.refreshDashboard(currentSku)
            _uiState.update { it.copy(isLoading = false) }
        } catch (e: Exception) {
            _uiState.update {
                it.copy(
                    isLoading = false,
                    error = e.message ?: "알 수 없는 에러",
                )
            }
        }
    }

    // 🔵 대시보드에서 "오차 보정" 버튼 눌렀을 때 호출
    fun applyCorrection() {
        val currentSku = _sku.value
        viewModelScope.launch {
            try {
                api.applyCorrection(
                    CorrectionRequest(sku_id = currentSku),
                )
                // 성공하면 굳이 UI를 건드리지 않아도,
                // 2초 폴링 루프에서 자동으로 최신 사이클/알람이 반영됨.
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        error = "보정 실패: ${e.message ?: "알 수 없는 에러"}",
                    )
                }
            }
        }
    }
}

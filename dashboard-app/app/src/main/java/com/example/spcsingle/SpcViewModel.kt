//spcviewmodel.kt
package com.example.spcsingle

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.spcsingle.data.repository.DashboardRepository
import com.example.spcsingle.data.repository.RepositoryProvider
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class DashboardUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val spcState: SpcStateEntity? = null,
    val alarms: List<AlarmEntity> = emptyList(),
    val cycles: List<CycleEntity> = emptyList(),
    val currentSku: String = ""
)

class SpcViewModel(
    application: Application
) : AndroidViewModel(application) {

    private val repository: DashboardRepository =
        RepositoryProvider.provide(application)

    // ✅ 처음엔 비워두고 서버 current_sku로 채움
    private val _sku = MutableStateFlow("")
    val sku: StateFlow<String> = _sku.asStateFlow()

    private val _uiState = MutableStateFlow(
        DashboardUiState(isLoading = true, currentSku = "")
    )
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        // 1) 앱 시작 시 current_sku 1회 로드 (fallback 포함)
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val serverSku = runCatching { repository.fetchCurrentSku() }.getOrNull()
            val initialSku = serverSku?.takeIf { it.isNotBlank() } ?: "COKE_355"

            _sku.value = initialSku
            _uiState.update { it.copy(currentSku = initialSku, isLoading = false) }
        }

        // 2) sku가 준비되면 해당 SKU로 대시보드 관측
        viewModelScope.launch {
            sku
                .filter { it.isNotBlank() }
                .distinctUntilChanged()
                .flatMapLatest { currentSku ->
                    _uiState.update { it.copy(isLoading = true, error = null, currentSku = currentSku) }
                    repository.observeDashboard(currentSku)
                }
                .catch { e ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            error = e.message ?: "네트워크 오류"
                        )
                    }
                }
                .collect { state ->
                    // repository가 만든 상태를 존중하되, currentSku는 항상 최신 sku로 보정
                    _uiState.value = state.copy(
                        currentSku = _sku.value.ifBlank { state.currentSku }
                    )
                }
        }

        // 3) ✅ RFID 태깅으로 서버 current_sku가 바뀌면 앱도 자동으로 SKU 변경 (폴링)
        viewModelScope.launch {
            while (isActive) {
                val serverSku = runCatching { repository.fetchCurrentSku() }.getOrNull()
                val s = serverSku?.trim().orEmpty()
                if (s.isNotBlank() && s != _sku.value) {
                    _sku.value = s
                }
                delay(800) // 0.8초마다 체크 (원하면 300~1000ms로 조절)
            }
        }

        // 4) ✅ 새 can_in/cycle이 계속 쌓이도록 화면도 주기 refresh (폴링)
        viewModelScope.launch {
            sku
                .filter { it.isNotBlank() }
                .distinctUntilChanged()
                .collectLatest { currentSku ->
                    while (isActive) {
                        runCatching { repository.refreshDashboard(currentSku) }
                        delay(800)
                    }
                }
        }
    }

    fun setSku(newSku: String) {
        val trimmed = newSku.trim()
        if (trimmed.isEmpty()) return
        _sku.value = trimmed
        _uiState.update { it.copy(currentSku = trimmed) }
    }

    fun refresh() {
        viewModelScope.launch {
            val s = _sku.value
            if (s.isNotBlank()) runCatching { repository.refreshDashboard(s) }
        }
    }

    fun applyCorrection() {
        viewModelScope.launch {
            val s = _sku.value
            if (s.isBlank()) return@launch

            _uiState.update { it.copy(isLoading = true, error = null) }
            val ok = runCatching { repository.applyCorrection(s) }.isSuccess
            if (!ok) {
                _uiState.update { it.copy(isLoading = false, error = "보정 요청 실패") }
                return@launch
            }
            // 보정 후 최신 반영
            runCatching { repository.refreshDashboard(s) }
            _uiState.update { it.copy(isLoading = false) }
        }
    }
}


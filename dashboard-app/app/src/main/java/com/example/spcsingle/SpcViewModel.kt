package com.example.spcsingle

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.spcsingle.data.repository.DashboardRepository
import com.example.spcsingle.data.repository.RepositoryProvider
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

// ----------------------------
// UI STATE
// ----------------------------
data class DashboardUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val spcState: SpcStateEntity? = null,
    val alarms: List<AlarmEntity> = emptyList(),
    val cycles: List<CycleEntity> = emptyList(),
    val currentSku: String = ""
)

// ----------------------------
// VIEWMODEL
// ----------------------------
class SpcViewModel(
    application: Application
) : AndroidViewModel(application) {

    private val repository: DashboardRepository =
        RepositoryProvider.provide(application)

    // ✅ 처음엔 비워두고, 앱 시작 시 서버 current_sku로 채움
    private val _sku = MutableStateFlow("")
    val sku: StateFlow<String> = _sku.asStateFlow()

    private val _uiState = MutableStateFlow(
        DashboardUiState(isLoading = true, currentSku = "")
    )
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        // ✅ 1) 앱 시작 시 서버에서 current_sku 먼저 받아서 세팅
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val serverSku = runCatching { repository.fetchCurrentSku() }.getOrNull()
            val initialSku = if (!serverSku.isNullOrBlank()) serverSku else "COKE_355" // fallback

            _sku.value = initialSku
            _uiState.update { it.copy(currentSku = initialSku, isLoading = false) }
        }

        // ✅ 2) sku가 준비되면 그 SKU로 대시보드 관측 시작
        viewModelScope.launch {
            sku
                .filter { it.isNotBlank() }
                .distinctUntilChanged()
                .onEach { newSku ->
                    _uiState.update { it.copy(isLoading = true, error = null, currentSku = newSku) }
                }
                .flatMapLatest { currentSku ->
                    repository.observeDashboard(currentSku)
                }
                .catch { e ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            error = e.message ?: "네트워크 오류",
                            currentSku = _sku.value
                        )
                    }
                }
                .collect { state ->
                    // repository가 만든 상태를 쓰되, currentSku는 현재 sku로 보정
                    _uiState.value = state.copy(
                        isLoading = false,
                        error = null,
                        currentSku = _sku.value
                    )
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
            if (s.isNotBlank()) repository.refreshDashboard(s)
        }
    }

    fun applyCorrection() {
        viewModelScope.launch {
            val s = _sku.value
            if (s.isNotBlank()) repository.applyCorrection(s)
        }
    }
}

package com.example.spcsingle

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.spcsingle.data.repository.DashboardRepository
import com.example.spcsingle.data.repository.RepositoryProvider
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

class SimulatorViewModel(
    application: Application
) : AndroidViewModel(application) {

    private val repository: DashboardRepository =
        RepositoryProvider.provide(application)

    private val _sku = MutableStateFlow("COKE_355")
    val sku: StateFlow<String> = _sku.asStateFlow()

    private val _uiState = MutableStateFlow(
        DashboardUiState(currentSku = "COKE_355")
    )
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            sku.flatMapLatest { repository.observeDashboard(it) }
                .collect { _uiState.value = it }
        }
    }

    fun setSku(newSku: String) {
        _sku.value = newSku
    }

    fun refresh() {
        viewModelScope.launch {
            repository.refreshDashboard(_sku.value)
        }
    }

    fun applyCorrection() {
        viewModelScope.launch {
            repository.applyCorrection(_sku.value)
        }
    }
}
package com.example.spcsingle

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.spcsingle.ui.theme.SpcsingleTheme
import android.util.Log

// 화면에 보이는 이름과 내부 ID를 분리
data class SkuOption(
    val id: String,    // 백엔드/UNO/DB 에 쓰는 값
    val label: String, // 화면에 보여줄 이름
)

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Log.e("DATA_SOURCE", BuildConfig.DATA_SOURCE)

        setContent {
            SpcsingleTheme {

                val dashboardVm: SpcViewModel = viewModel()

                val dashboardState by dashboardVm.uiState.collectAsState()
                val currentSku by dashboardVm.sku.collectAsState()

                MainScreen(
                    dashboardState = dashboardState,
                    sku = currentSku,
                    onDashboardRefresh = { dashboardVm.refresh() },
                    onSkuChange = { dashboardVm.setSku(it) },
                    onApplyCorrection = { dashboardVm.applyCorrection() },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    dashboardState: DashboardUiState,
    sku: String,
    onDashboardRefresh: () -> Unit,
    onSkuChange: (String) -> Unit,
    onApplyCorrection: () -> Unit,
) {
    // 내부 ID는 CIDER_500, 화면 표시 이름은 CIDER_355
    val skuOptions = listOf(
        SkuOption(id = "COKE_355",  label = "COKE_355"),
        SkuOption(id = "CIDER_500", label = "CIDER_355"),
    )

    // 현재 sku(id)에 대응되는 라벨
    val currentSkuLabel = skuOptions.firstOrNull { it.id == sku }?.label ?: sku

    var expanded by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text("SmartCan SPC Dashboard") },
                )

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text("현재 SKU: $currentSkuLabel", fontWeight = FontWeight.Bold)

                    Box {
                        Button(onClick = { expanded = true }) {
                            Text("SKU 변경")
                        }
                        DropdownMenu(
                            expanded = expanded,
                            onDismissRequest = { expanded = false },
                        ) {
                            skuOptions.forEach { option ->
                                DropdownMenuItem(
                                    text = { Text(option.label) },
                                    onClick = {
                                        // 화면엔 355, 내부에선 500 같은 ID로 전달
                                        onSkuChange(option.id)
                                        expanded = false
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            DashboardScreen(
                state = dashboardState,
                onRefresh = onDashboardRefresh,
                onApplyCorrection = onApplyCorrection,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    state: DashboardUiState,
    onRefresh: () -> Unit,
    onApplyCorrection: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("SmartCan SPC Dashboard") },
                actions = {
                    TextButton(onClick = onRefresh) {
                        Text("새로고침")
                    }
                },
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {

            if (state.isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }

            state.error?.let { msg ->
                Text(
                    text = "에러: $msg",
                    color = MaterialTheme.colorScheme.error,
                )
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("현재 SPC 상태", fontWeight = FontWeight.Bold)

                    val spc = state.spcState
                    if (spc == null) {
                        Text("데이터 없음")
                    } else {
                        Text("state: ${spc.spcState}")
                        Text("alarm_type: ${spc.alarmType ?: "-"}")
                        Text("cusum_pos: ${spc.cusumPos ?: 0.0}")
                        Text("cusum_neg: ${spc.cusumNeg ?: 0.0}")
                        Text("n_samples: ${spc.nSamples ?: 0}")
                    }
                }
            }

            // UNO 파란불 + 355 트리거 버튼
            Button(
                onClick = onApplyCorrection,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("오차 보정 적용 (UNO 파란불 + 355)")
            }

            Text("최근 캔 로그", fontWeight = FontWeight.Bold)
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(180.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.cycles) { cycle ->
                    // 로그에서도 CIDER_500 → CIDER_355 로 표기
                    val skuLabel =
                        if (cycle.sku == "CIDER_500") "CIDER_355" else cycle.sku

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            modifier = Modifier.padding(8.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text("seq=${cycle.seq}, sku=$skuLabel")
                            Text("target=${cycle.targetMl}, actual=${cycle.actualMl ?: "-"}")
                            Text("error=${cycle.error ?: "-"}, spc=${cycle.spcState ?: "-"}")
                            Text("time=${cycle.createdAt}")
                        }
                    }
                }
            }

            Text("최근 알람", fontWeight = FontWeight.Bold)
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.alarms) { alarm ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text("[${alarm.level}] ${alarm.alarmType ?: "-"}")
                            Text(alarm.message ?: "(메시지 없음)")
                            Text("created_at: ${alarm.createdAt}")
                        }
                    }
                }
            }
        }
    }
}
package com.example.spcsingle

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface SpcApi {

    // ===== SPC / Quality =====

    @GET("quality/spc_state")
    suspend fun getSpcCurrent(
        @Query("sku") sku: String,
    ): SpcCurrentDto

    @GET("quality/spc_states")
    suspend fun getSpcHistory(
        @Query("sku") sku: String,
        @Query("limit") limit: Int = 50,
    ): List<SpcStateDto>

    // ===== Alarms =====

    @GET("alarms/recent")
    suspend fun getAlarms(
        @Query("sku") sku: String,
        @Query("limit") limit: Int = 50,
    ): List<AlarmDto>

    @GET("alarms/{id}")
    suspend fun getAlarmDetail(
        @Path("id") id: Long,
    ): AlarmDto

    // ===== Cycles (최근 캔 로그) =====

    @GET("cycles/")
    suspend fun getRecentCycles(
        @Query("sku") sku: String,
        @Query("limit") limit: Int = 30,
    ): List<CycleDto>

    // ===== Control – 센서 시뮬레이터: 사이클 실행 =====

    @GET("control/current_sku")
    suspend fun getCurrentSku(): CurrentSkuDto

    @POST("control/fill")
    suspend fun runCycle(
        @Body body: RunCycleRequest,
    ): RunCycleResponse

    // 🔵 Control – 자동 오차 보정 + UNO에 CORR 보내기
    @POST("control/apply_correction")
    suspend fun applyCorrection(
        @Body body: CorrectionRequest,
    ): CorrectionResponse

    companion object {
        private const val BASE_URL = "http://10.0.2.2:8000/api/v1/"

        fun create(): SpcApi =
            Retrofit.Builder()
                .baseUrl(BASE_URL)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(SpcApi::class.java)
    }
}

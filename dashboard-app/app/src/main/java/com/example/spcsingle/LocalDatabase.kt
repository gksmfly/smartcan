// UI cache / offline fallback only
//LocalDatabase.kt
package com.example.spcsingle

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

// ---------- Entities ----------

@Entity(tableName = "cycles")
data class CycleEntity(
    @PrimaryKey val id: Long,
    val sku: String,
    val seq: Int,
    val targetMl: Double,
    val actualMl: Double?,
    val valveMs: Int?,
    val error: Double?,
    val spcState: String?,
    val createdAt: String,
)

@Entity(tableName = "spc_states")
data class SpcStateEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val sku: String,
    val spcState: String,
    val alarmType: String?,
    val mean: Double?,
    val std: Double?,
    val cusumPos: Double?,
    val cusumNeg: Double?,
    val nSamples: Int?,
    val createdAt: String,
)

@Entity(tableName = "alarms")
data class AlarmEntity(
    @PrimaryKey val id: Long,
    val sku: String,
    val level: String,
    val alarmType: String?,
    val message: String?,
    val cycleId: Long?,
    val spcStateId: Long?,
    val createdAt: String,
)


// ---------- DAOs ----------

@Dao
interface CycleDao {

    @Query("SELECT * FROM cycles WHERE sku = :sku ORDER BY createdAt DESC LIMIT :limit")
    fun getRecentCycles(sku: String, limit: Int): Flow<List<CycleEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(cycles: List<CycleEntity>)
}

@Dao
interface SpcStateDao {

    @Query("SELECT * FROM spc_states WHERE sku = :sku ORDER BY createdAt DESC LIMIT 1")
    fun getLatestState(sku: String): Flow<SpcStateEntity?>

    @Insert
    suspend fun insert(state: SpcStateEntity)
}

@Dao
interface AlarmDao {

    @Query("SELECT * FROM alarms WHERE sku = :sku ORDER BY createdAt DESC LIMIT :limit")
    fun getRecentAlarms(sku: String, limit: Int): Flow<List<AlarmEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(alarms: List<AlarmEntity>)
}


// ---------- Database ----------

@Database(
    entities = [CycleEntity::class, SpcStateEntity::class, AlarmEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun cycleDao(): CycleDao
    abstract fun spcStateDao(): SpcStateDao
    abstract fun alarmDao(): AlarmDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE
                    ?: Room.databaseBuilder(
                        context.applicationContext,
                        AppDatabase::class.java,
                        "smartcan.db",
                    )
                        .createFromAsset("smartcan.db") // ⭐ assets에서 DB 복사
                        .fallbackToDestructiveMigration()
                        .build()
                        .also { INSTANCE = it }
            }
        }
    }
}


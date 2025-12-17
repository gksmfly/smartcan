package com.example.spcsingle.mqtt

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.eclipse.paho.android.service.MqttAndroidClient
import org.eclipse.paho.client.mqttv3.*

class MqttManager(context: Context) {

    companion object {
        private const val TAG = "MqttManager"
        private const val MQTT_URL = "tcp://10.0.2.2:1883"
        private const val CLIENT_ID = "android-client"
        private const val TOPIC_CAN_IN = "line1/event/can_in"
    }

    private val appContext = context.applicationContext

    private val client: MqttAndroidClient =
        MqttAndroidClient(appContext, MQTT_URL, CLIENT_ID)

    private val _detectedSku = MutableStateFlow<String?>(null)
    val detectedSku: StateFlow<String?> = _detectedSku

    fun connect() {
        if (client.isConnected) return

        val options = MqttConnectOptions().apply {
            isAutomaticReconnect = true
            isCleanSession = true
        }

        client.setCallback(object : MqttCallback {
            override fun connectionLost(cause: Throwable?) {
                Log.w(TAG, "MQTT connection lost", cause)
            }

            override fun messageArrived(topic: String?, message: MqttMessage?) {
                val payload = message?.toString() ?: return
                Log.d(TAG, "MQTT recv topic=$topic payload=$payload")

                if (topic == TOPIC_CAN_IN) {
                    try {
                        val json = org.json.JSONObject(payload)
                        val sku = json.optString("sku", "")
                        if (sku.isNotEmpty()) {
                            _detectedSku.value = sku
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "JSON parse error", e)
                    }
                }
            }

            override fun deliveryComplete(token: IMqttDeliveryToken?) {
                // publish 안 쓰면 비워둬도 됨
            }
        })

        try {
            client.connect(options, null, object : IMqttActionListener {
                override fun onSuccess(asyncActionToken: IMqttToken?) {
                    Log.d(TAG, "MQTT connected")
                    try {
                        client.subscribe(TOPIC_CAN_IN, 1, null, null)
                        Log.d(TAG, "Subscribed: $TOPIC_CAN_IN")
                    } catch (e: MqttException) {
                        Log.e(TAG, "subscribe error", e)
                    }
                }

                override fun onFailure(asyncActionToken: IMqttToken?, exception: Throwable?) {
                    Log.e(TAG, "MQTT connect failed", exception)
                }
            })
        } catch (e: Exception) {
            Log.e(TAG, "MQTT connect() threw", e)
        }
    }

    fun disconnect() {
        try {
            if (client.isConnected) {
                client.disconnect()
            }
        } catch (e: Exception) {
            Log.e(TAG, "disconnect error", e)
        }
    }
}

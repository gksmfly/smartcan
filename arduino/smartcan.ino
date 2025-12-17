#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <TM1637Display.h>
#include <LiquidCrystal_I2C.h>

// ===================== 핀 배치 =====================
#define RST_PIN   9
#define SS_PIN    10
#define SEG_CLK   A2
#define SEG_DIO   A3
#define VALVE_PIN 4
#define LED_BLUE   2
#define LED_RED    3
#define LED_YELLOW 5
#define LED_GREEN  7
#define BUZZ_PIN   6

// ===================== 객체 =====================
MFRC522 mfrc522(SS_PIN, RST_PIN);
TM1637Display display(SEG_CLK, SEG_DIO);
LiquidCrystal_I2C* lcd = nullptr;

bool lcdReady = false;
String pcLine;

long lastSeq = 0;
String lastSku = "UNKNOWN";
float lastTargetMl = 0.0;

unsigned long lastHB = 0;

// 🔥 체인지오버/보정 시나리오 플래그
bool changeoverPending = false;   // 다음 태깅에서 BAD FILL 데모
bool correctionPending = false;   // CORR 이후 다음 F 명령은 무조건 OK

// ===================== 유틸 =====================
String uidToSku(const String& uid) {
  static bool cokeFirstSeen = false;

  if (uid == "EA4ED605") {
    if (!cokeFirstSeen) {
      cokeFirstSeen = true;
      return "COKE_355";
    } else {
      return "CIDER_500";
    }
  }
  return "UNKNOWN";
}

void beepSuccess(){
  digitalWrite(BUZZ_PIN, HIGH);
  delay(120);
  digitalWrite(BUZZ_PIN, LOW);
}

void clearStatusLEDs(){
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN, LOW);
}

void setRunLED(){ clearStatusLEDs(); digitalWrite(LED_GREEN, HIGH); }
void setErrorLED(){ clearStatusLEDs(); digitalWrite(LED_RED, HIGH); }
void setChangeoverLED(){ clearStatusLEDs(); digitalWrite(LED_YELLOW, HIGH); }
void setBlueLED(bool on){ digitalWrite(LED_BLUE, on ? HIGH : LOW); }

void sendMqttPublish(const String& topic, const String& payload){
  String line = "P:" + topic + ":" + payload;
  Serial.println(line);
}

void lcdShowFillProgress(float target_ml, float current_ml){
  if(!lcdReady || !lcd) return;

  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print("TARGET:");
  lcd->print(target_ml, 0);
  lcd->print("ml");

  lcd->setCursor(0, 1);
  lcd->print("NOW:");
  lcd->print(current_ml, 0);
  lcd->print("ml");
}

// 🔵 CORR 상태 표시: 파란불 + 355 / 355
// 🔵 CORR 상태 표시: 파란불 -> 잠시 후 초록불
void showCorrectedState(){
  float target_ml = 355.0;

  // 1) 우선 파란불 + 355 / 355 상태로 보여주기
  clearStatusLEDs();
  setBlueLED(true);  // 파란 LED ON

  display.showNumberDec((int)(target_ml + 0.5f), true);
  lcdShowFillProgress(target_ml, target_ml);

  // 파란 상태를 1.5초 정도 유지 (원하면 시간 조절)
  delay(1500);

  // 2) 파란불 끄고 정상(초록)으로 전환
  setBlueLED(false);
  setRunLED();  // 초록 LED ON

  // 초록 상태에서도 355 / 355 유지
  display.showNumberDec((int)(target_ml + 0.5f), true);
  lcdShowFillProgress(target_ml, target_ml);
}


// CIDER일 때는 2번째 줄을 'CIDER:355'로 바꿈
void lcdShowRfidOk(const String& uid, const String& sku){
  if(!lcdReady || !lcd) return;

  lcd->clear();
  lcd->setCursor(0,0);
  lcd->print("RFID OK");
  lcd->setCursor(0,1);

  if (sku == "CIDER_500") {
    lcd->print("CIDER:355");
  } else {
    lcd->print("SKU:");
    lcd->print(sku);
  }
  delay(1200);
}

// ===================== RFID 읽기 =====================
void checkRFID(){
  if(!mfrc522.PICC_IsNewCardPresent()) return;
  delay(50);

  if(!mfrc522.PICC_ReadCardSerial()){
    Serial.println("[RFID] Read fail");
    delay(200);
    return;
  }

  String uidStr="";
  for(byte i=0;i<mfrc522.uid.size;i++){
    if(mfrc522.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();

  String newSku = uidToSku(uidStr);

  static long seq = 0;

  // ==========================================================
  // 1) 체인지오버 이후 "다음 태깅"에서 BAD FILL (355 vs 344) 데모
  // ==========================================================
  if (changeoverPending) {
    changeoverPending = false;

    seq++;
    lastSeq      = seq;
    lastSku      = newSku;
    lastTargetMl = 355.0;   // 항상 355 타깃

    float target_ml = 355.0;
    float actual_ml = 344.0;  // 시나리오용 고정 값

    Serial.println("[RFID] After changeover -> BAD FILL DEMO (T=355, NOW=344)");

    // 비정상 충전 "시작"할 때 부저
    beepSuccess();

    // ---- 충전 중 애니메이션 (0 -> 344, 파란불 깜빡) ----
    const int steps = 20;
    for (int i = 0; i <= steps; i++) {
      float now_ml = (actual_ml * i) / steps;
      display.showNumberDec((int)(now_ml + 0.5f), true);
      setBlueLED((i % 2) == 0);
      lcdShowFillProgress(target_ml, now_ml);
      delay(150);
    }
    setBlueLED(false);

    // ---- 충전 완료: 빨간 LED ----
    setErrorLED();

    // LCD에 최종 T:355 / NOW:344 표시
    if (lcdReady && lcd) {
      lcd->clear();
      lcd->setCursor(0, 0);
      if (newSku == "CIDER_500") {
        lcd->print("CIDER T:");
      } else if (newSku == "COKE_355") {
        lcd->print("COKE T:");
      } else {
        lcd->print("ERR T:");
      }
      lcd->print(target_ml, 0);

      lcd->setCursor(0, 1);
      lcd->print("NOW:");
      lcd->print(actual_ml, 0);
    }

    // 백엔드 데모용 fill_result
    String json="{";
    json += "\"seq\":"+String(seq)+",";
    json += "\"sku\":\""+newSku+"\",";
    json += "\"actual_ml\":"+String(actual_ml,1)+",";
    json += "\"target_ml\":"+String(target_ml,1)+",";
    json += "\"valve_ms\":0,";
    json += "\"status\":\"ERR\"}";
    sendMqttPublish("line1/event/fill_result", json);

    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();

    delay(3000);
    return;
  }

  // ==========================================================
  // 2) 이번 태깅에서 체인지오버 발생 (노란 LED)
  // ==========================================================
  if (lastSku != "UNKNOWN" && newSku != lastSku) {
    Serial.println("[RFID] Changeover detected!");
    setChangeoverLED();
    delay(5000);
    clearStatusLEDs();
    changeoverPending = true;   // 다음 태깅에서 BAD FILL
  }

  // ==========================================================
  // 3) 일반 RFID OK 처리 (부저 삑)
  // ==========================================================
  seq++;

  float target_ml = 355.0;

  lastSeq      = seq;
  lastSku      = newSku;
  lastTargetMl = target_ml;

  // CAN_IN MQTT publish
  String json2 = "{\"seq\":"+String(seq)+",\"uid\":\""+uidStr+"\",\"sku\":\""+newSku+
                "\",\"target_ml\":"+String(target_ml,1)+"}";
  sendMqttPublish("line1/event/can_in", json2);

  beepSuccess();
  lcdShowRfidOk(uidStr, newSku);
  display.showNumberDec(0, true);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(300);
}

// ===================== FILL CMD 처리 =====================
void handleFillCommand(const String& line){
  int idx1=line.indexOf(',');
  int idx2=line.indexOf(',', idx1+1);
  int idx3=line.indexOf(',', idx2+1);
  int idx4=line.indexOf(',', idx3+1);

  long seq       = line.substring(idx1+1, idx2).toInt();
  float target_ml= line.substring(idx2+1, idx3).toFloat();
  String mode    = line.substring(idx3+1, idx4);
  long valve_ms  = line.substring(idx4+1).toInt();

  clearStatusLEDs();

  digitalWrite(VALVE_PIN, HIGH);
  setBlueLED(true);

  unsigned long start = millis();
  float current_ml = 0.0;
  bool flip = true;

  while(millis() - start < valve_ms){
    float ratio = float(millis() - start) / float(valve_ms);
    if(ratio > 1.0) ratio = 1.0;

    current_ml = target_ml * ratio;

    display.showNumberDec((int)(current_ml + 0.5f), true);
    flip = !flip;
    setBlueLED(flip);

    lcdShowFillProgress(target_ml, current_ml);
    delay(120);
  }

  digitalWrite(VALVE_PIN, LOW);
  setBlueLED(false);

  float actual_ml = 0.0;

  if(lastSku == "COKE_355" || lastSku == "CIDER_500"){
    float max_ml = target_ml;
    float base_ms = 1000.0;

    float ratio = (float)valve_ms / base_ms;
    if(ratio > 1.0) ratio = 1.0;
    if(ratio < 0.0) ratio = 0.0;

    actual_ml = max_ml * ratio;
    if(actual_ml < 0) actual_ml = 0;
    if(actual_ml > max_ml) actual_ml = max_ml;
  } else {
    actual_ml = target_ml;
  }

  // 🔵 CORR 이후 첫 F 명령이면 강제로 정상 샷으로 맞추기
  if (correctionPending) {
    Serial.println("[FILL] correctionPending -> force OK fill");
    actual_ml = target_ml;      // 355 그대로
    correctionPending = false;  // 한 번만 적용
  }

  lcdShowFillProgress(target_ml, actual_ml);

  unsigned long segStart = millis();
  while(millis() - segStart < 5000){
    display.showNumberDec((int)(actual_ml + 0.5f), true);
    delay(200);
  }

  float diff = actual_ml - target_ml;
  if(diff < 0) diff = -diff;
  float tol = target_ml * 0.05f;

  String status = "OK";
  if (diff > tol) {
    status = "ERR";
  }

  if (mode.equalsIgnoreCase("ERROR")) {
    status = "ERR";
  }

  if (status == "OK") {
    setRunLED();    // ✅ 초록 불
  } else {
    setErrorLED();
  }

  Serial.print("[FILL] sku=");
  Serial.print(lastSku);
  Serial.print(" target=");
  Serial.print(target_ml);
  Serial.print(" actual=");
  Serial.print(actual_ml);
  Serial.print(" diff=");
  Serial.print(diff);
  Serial.print(" tol=");
  Serial.print(tol);
  Serial.print(" mode=");
  Serial.print(mode);
  Serial.print(" status=");
  Serial.println(status);

  String json3="{";
  json3+="\"seq\":"+String(seq)+",";
  json3+="\"sku\":\""+lastSku+"\",";
  json3+="\"actual_ml\":"+String(actual_ml,1)+",";
  json3+="\"target_ml\":"+String(target_ml,1)+",";
  json3+="\"valve_ms\":"+String(valve_ms)+",";
  json3+="\"status\":\""+status+"\"}";
  sendMqttPublish("line1/event/fill_result", json3);
}

// ===================== PC 명령 처리 =====================
void handleFromPc(){
  while(Serial.available()){
    char c = Serial.read();
    if(c == '\n'){
      pcLine.trim();

      if(pcLine.length() > 0){
        Serial.print("[PC] cmd=");
        Serial.println(pcLine);
      }

      if(pcLine.startsWith("F,")) {
        handleFillCommand(pcLine);
      }
      // CORR 명령: 파란불 + 355/355, 다음 F 는 무조건 초록 OK
      // CORR 명령: 파란불 + 355/355, 다음 F 는 무조건 초록 OK
      else if (pcLine.equalsIgnoreCase("CORR")) {
        Serial.println("[PC] CORR received -> showCorrectedState");
        correctionPending = true;   // ✅ 이 줄 추가 (핵심)
        showCorrectedState();
      }

      pcLine="";
    }
    else if(c != '\r'){
      pcLine += c;
    }
  }
}

// ===================== setup =====================
void setup(){
  Serial.begin(9600);
  delay(1000);

  Wire.begin();
  byte addrs[2] = {0x27,0x3F};
  byte found = 0;

  for(int i=0;i<2;i++){
    Wire.beginTransmission(addrs[i]);
    if(Wire.endTransmission()==0){ found = addrs[i]; break; }
  }

  if(found != 0){
    lcd = new LiquidCrystal_I2C(found, 16, 2);
    lcd->init();
    lcd->backlight();
    lcd->clear();
    lcd->setCursor(0,0);
    lcd->print("SmartCan UNO");
    lcd->setCursor(0,1);
    lcd->print("READY");
    lcdReady = true;
  }

  delay(1500);

  display.setBrightness(0x0f);
  display.showNumberDec(0, true);

  SPI.begin();
  mfrc522.PCD_Init();

  pinMode(VALVE_PIN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  clearStatusLEDs();

  randomSeed(analogRead(A0));

  Serial.println("=== SmartCan UNO READY ===");
  lastHB = millis();
}

// ===================== loop =====================
void loop(){
  checkRFID();
  handleFromPc();

  if(millis() - lastHB > 5000){
    Serial.println("[HB] loop alive");
    lastHB = millis();
  }
}

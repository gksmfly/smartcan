// Firebase flavor 전용 Gradle 설정
plugins {
    id("com.google.gms.google-services")
}

dependencies {
    implementation("com.google.firebase:firebase-firestore-ktx:25.0.0")
}

// build.gradle.kts (Project: spcsingle)

plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "2.0.0" apply false
    // ★ 여기 추가
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.0" apply false
}

buildscript {
    dependencies {
        classpath("com.google.gms:google-services:4.4.2")
    }
}
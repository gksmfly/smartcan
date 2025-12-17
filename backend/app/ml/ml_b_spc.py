import numpy as np


def compute_spc_cusum(
    errors,
    k: float = 0.5,
    h_warn: float = 1.0,
    h_alarm: float = 2.0,
):
    """SPC/CUSUM 기반 품질 상태 판단.

    errors : 최근 오차(error_ml) 1D 배열
    k      : reference value (타깃 편차)
    h_warn : WARN 임계값
    h_alarm: ALARM 임계값

    반환 값:
      {
        "spc_state": "OK" | "WARN" | "ALARM",
        "alarm_type": "POS_DRIFT" | "NEG_DRIFT" | None,
        "mean": float,
        "std": float,
        "cusum_pos": float,
        "cusum_neg": float,
      }
    """
    errors = np.asarray(errors, dtype=float)

    if errors.size == 0:
        return {
            "spc_state": "UNKNOWN",
            "alarm_type": None,
            "mean": 0.0,
            "std": 0.0,
            "cusum_pos": 0.0,
            "cusum_neg": 0.0,
        }

    # 기본 통계
    mean = float(np.mean(errors))
    std = float(np.std(errors) + 1e-6)  # 분산 0 방지용 epsilon

    # 표준화한 잔차 값
    z = (errors - mean) / std

    c_pos = 0.0
    c_neg = 0.0
    spc_state = "OK"
    alarm_type = None

    for v in z:
        c_pos = max(0.0, c_pos + v - k)
        c_neg = min(0.0, c_neg + v + k)

        # ALARM 상태가 최고 우선순위
        if c_pos > h_alarm or c_neg < -h_alarm:
            spc_state = "ALARM"
            alarm_type = "POS_DRIFT" if c_pos > h_alarm else "NEG_DRIFT"
            break
        # 아직 ALARM 아니고, WARN 임계값만 넘은 경우
        elif spc_state != "ALARM" and (c_pos > h_warn or c_neg < -h_warn):
            spc_state = "WARN"
            alarm_type = "POS_DRIFT" if c_pos > h_warn else "NEG_DRIFT"

    return {
        "spc_state": spc_state,
        "alarm_type": alarm_type,
        "mean": mean,
        "std": std,
        "cusum_pos": float(c_pos),
        "cusum_neg": float(c_neg),
    }

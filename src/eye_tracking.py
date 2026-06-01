import time

import cv2

from src.vision.eye_tracking_core import detect_gaze_direction


def main():
    cap = cv2.VideoCapture(0)
    last_print_time = time.time()
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            direction = detect_gaze_direction(frame)

            # 5초마다 터미널 출력(라즈베리에서도 부담 적게)
            current_time = time.time()
            if current_time - last_print_time >= 5:
                print("현재 시선 방향 :", direction)
                last_print_time = current_time

            cv2.putText(
                frame,
                f"GAZE : {direction}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

            cv2.imshow("Gaze Tracking (Debug)", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
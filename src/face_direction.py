import cv2

from src.vision.face_direction_core import detect_face_direction


def main():
    cap = cv2.VideoCapture(0)
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            direction = detect_face_direction(frame)

            cv2.putText(
                frame,
                f"FACE DIRECTION : {direction}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            print(direction)
            cv2.imshow("Face Direction Tracking", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
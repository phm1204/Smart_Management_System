import cv2

# =========================
# 얼굴 검출기
# =========================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades +
    'haarcascade_frontalface_default.xml'
)

# =========================
# 웹캠 시작
# =========================
cap = cv2.VideoCapture(0)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    frame_h, frame_w = frame.shape[:2]

    screen_center_x = frame_w // 2
    screen_center_y = frame_h // 2

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=8,
        minSize=(200, 200)
    )

    direction = "NO FACE"

    for (x, y, w, h) in faces:

        # 얼굴 박스
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (255, 0, 0),
            2
        )

        # 얼굴 중심점
        face_center_x = x + w // 2
        face_center_y = y + h // 2

        # 중심점 표시
        cv2.circle(
            frame,
            (face_center_x, face_center_y),
            5,
            (0, 0, 255),
            -1
        )

        # =========================
        # 방향 판단
        # =========================
        direction = "CENTER"

        # 좌우 방향
        if face_center_x < screen_center_x - 100:
            direction = "LEFT"

        elif face_center_x > screen_center_x + 100:
            direction = "RIGHT"

        # 아래 방향(책 보기)
        if face_center_y > screen_center_y + 80:
            direction = "DOWN"

        break

    # =========================
    # 방향 출력
    # =========================
    cv2.putText(
        frame,
        f"FACE DIRECTION : {direction}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    print(direction)

    cv2.imshow(
        "Face Direction Tracking",
        frame
    )

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
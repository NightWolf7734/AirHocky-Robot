# coding=utf-8
# imports
from collections import deque
from imutils.video import VideoStream
import numpy as np
import argparse
import cv2
import imutils
import time
import math as m
import serial

# Verbindungsaufbau zum Arduino
ser = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(5)

# Die groben Randbegrenzungen des Tisches für die Richtungsberechnung später
xBegrenzungR = 525
xBegrenzungL = 360
yBegrenzungTop = 20
yBegrenzungBot = 320

# Definition des HSV-Blau-Bereichs, in dem sich der Pusher befindet
blueLower = np.array([100,150,0])
blueUpper = np.array([140,255,255])

# Definition des HSV-Grün-Bereichs, in dem sich der Puk befindet
greenLower = np.array([29,86,6])
greenUpper = np.array([64,255,255])

# Zur Info für den Nutzer
print("Start")

# nehme Bild der angeschlossenen Raspberry Pi Kamera
cap = cv2.VideoCapture(0)

# Erstelle eine Liste, die später die Positionen des Puks speichert
listPointsPuk = deque(maxlen=3)

# Prüfung, ob die Kamera erfolgreich geöffnet wurde
if (cap.isOpened()== False): 
  print("Error opening video stream or file")

i = 0
centerNeu = (0,0)

# Solange die Kamera Bilder liefert in der Schleife bleiben
while(cap.isOpened()):
    # Das aktuelle Kamerabild nehmen
    ret, frame = cap.read()
    i = i+1
    modVar = i % 3
    # Jedes 3. Bild soll verarbeitet werden. Das entspricht einer Zeit zwischen den Bildern von einer Zehntel Sekunde
    if (modVar == 0):
        # Prüfe, ob Bild und Daten richtig aufgenommen wurden
        if (ret is False):
            print('false ret')
            break
        if frame is None:
            print("no frame")
            break
        # Bild wird zugeschnitten und auf eine Weite von 600px festgelegt
        # Ein Gaussfilter glättet das Bild und sorgt für weniger Ausreißer
        # Der Frabraum HSV wird festgelegt 
        frame = frame[70:385, 80:600]
        frame = imutils.resize(frame, width=600)
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
       
        # Es wird jeweils eine Maske für Blau und Grün inm Bild erstellt
        maskBlue = cv2.inRange(hsv, blueLower, blueUpper)
        maskGreen = cv2.inRange(hsv, greenLower, greenUpper)
        # Auf beide Maskenbilder wird anschließend Erosion und Dilattation angewandt, 
        # dies sorgt für die Herausfilterung von Ausreißern und klarere Masken
        maskGreen = cv2.erode(maskGreen, None, iterations=2)
        maskGreen = cv2.dilate(maskGreen, None, iterations=2)
        maskBlue = cv2.erode(maskBlue, None, iterations=2)
        maskBlue = cv2.dilate(maskBlue, None, iterations=2)

        # In der Maske zunächst der Puk als grüne Kontur gefunden werden
        # Der Mittelpunkt des gefundenen Kreises soll in die Variable center gespeichert werden
        cnts = cv2.findContours(maskGreen.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        center = None

        # wenn ein Kreis gefunden wurde
        if len(cnts) > 0:
            # Finde die größte Kontur
            # Berechne den Mittelpunkt und den groben Umkreis der Kontur
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            # Wenn der Radius der Kontur größer 5 ist, wird mit der Kontur fortgefahren
            if radius > 5:
                # TODO raus? Male: Kreis um den Puk, den Mittelpunkt des Puks
                cv2.circle(frame, (int(x), int(y)), int(radius),
                    (0, 255, 255), 2)
                cv2.circle(frame, center, 5, (0, 0, 255), -1)

            # Falls bereits mind. ein Standort des Puks in der Liste ist
            if listPointsPuk:
                centerAlt = listPointsPuk[0]
                if centerAlt != None:
                    # Richtung des Puks wird ermittelt, indem der vorherige Standort vom aktuellen Standort abgezogen wird
                    richtungsvektor = (center[0] - centerAlt[0], center[1] - centerAlt[1])
                    
                    # Wo wird der Puk in einer Sekunde sein?
                    centerNeu = (center[0] + (richtungsvektor[0] * 30), center[1] + (richtungsvektor[1] * 30))

                    centerX = centerNeu[0]
                    centerY = centerNeu[1]

                    # Begrenzung wird berechnet. Puscher darf nicht über den Tisch hinaus
                    if centerNeu[0] < xBegrenzungL:
                        centerX = xBegrenzungL

                    if centerNeu[0] > xBegrenzungR:
                        centerX = xBegrenzungR

                    if centerNeu[1] < yBegrenzungTop:
                        centerY = yBegrenzungTop

                    if centerNeu[1] > yBegrenzungBot:
                        centerY = yBegrenzungBot

                    centerNeu = (centerX, centerY)

        # Hänge jetzige Position an die Liste an, um beim nächsten Bild Richtung des Puks erneut zu berechnen
        listPointsPuk.appendleft(center)

        # Center mitte des Puks, wird für die Berechnung wo der Puscher hinfahren muss
        # In der Maske wird jetzt der Pusher als blaue Kontur gefunden
        # Der Mittelpunkt des gefundenen Kreises soll in die Variable centerPusher gespeichert werden
        cntsP = cv2.findContours(maskBlue.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)
        cntsP = imutils.grab_contours(cntsP)
        centerPusher = None

        # wenn ein Kreis gefunden wurde
        if len(cntsP) > 0:
            # Finde die größte Kontur
            # Berechne den Mittelpunkt und den groben Umkreis der Kontur
            cP = max(cntsP, key=cv2.contourArea)
            ((x1, y1), radiusP) = cv2.minEnclosingCircle(cP)
            MP = cv2.moments(cP)
            centerPusher = (int(MP["m10"] / MP["m00"]), int(MP["m01"] / MP["m00"]))
            # Wenn der Radius der Kontur größer 10 ist, wird mit der Kontur fortgefahren
            if radiusP > 10:
                # TODO raus? Male: Kreis um den Puk, den Mittelpunkt des Puks
                cv2.circle(frame, (int(x1), int(y1)), int(radiusP),
                    (255, 0, 0), 2)
                cv2.circle(frame, centerPusher, 5, (0, 0, 255), -1)

                # Schicken der nötigen Richtung des Pushers an den Arduino
                if (centerNeu[0] == centerPusher[0] and centerNeu[1] == centerPusher[1]):
                    ser.write(b"0\n")
                elif(centerNeu[0] > centerPusher[0] and centerNeu[1] > centerPusher[1]):
                    ser.write(b"1\n")
                elif(centerNeu[0] < centerPusher[0] and centerNeu[1] > centerPusher[1]):
                    # Gehe sicher, dass der Pusher nicht über die Mittellinie hinaus geht
                    if centerNeu[0] < 320:
                        ser.write(b"0\n")
                    elif centerNeu[0] >= 320:
                        ser.write(b"2\n")
                elif(centerNeu[0] > centerPusher[0] and centerNeu[1] < centerPusher[1]):
                    ser.write(b"3\n")
                elif(centerNeu[0] < centerPusher[0] and centerNeu[1] < centerPusher[1]):
                    if centerNeu[0] < 320:
                        ser.write(b"0\n")
                    elif centerNeu[0] >= 320:
                        ser.write(b"4\n")
                elif(centerNeu[0] == centerPusher[0] and centerNeu[1] > centerPusher[1]):
                    ser.write(b"5\n")
                elif(centerNeu[0] == centerPusher[0] and centerNeu[1] < centerPusher[1]):
                    ser.write(b"6\n")
                elif(centerNeu[0] > centerPusher[0] and centerNeu[1] == centerPusher[1]):
                    ser.write(b"7\n")
                elif(centerNeu[0] < centerPusher[0] and centerNeu[1] == centerPusher[1]):
                    if centerNeu[0] < 320:
                        ser.write(b"0\n")
                    elif centerNeu[0] >= 320:
                        ser.write(b"8\n")

        
        # Anzeige des Programms auf dem Bildschirm - Für Testzwecke
        # cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF
        # Software - Notaus: Wird bei angeschlossener Tastatur "q" gedrückt, stoppen die Motoren und das Programm
        if key == ord("s"):
            # Pusher soll auf seine Startposition fahren
            centerStart = (450,150)
            while (centerPusher[0] != centerStart[0] and centerPusher[1] != centerStart[1]):
                if (centerStart[0] == centerPusher[0] and centerStart[1] == centerPusher[1]):
                    ser.write(b"0\n")
                    print("00")
                elif(centerStart[0] > centerPusher[0] and centerStart[1] > centerPusher[1]):
                    ser.write(b"1\n")
                    print("xy")
                elif(centerStart[0] < centerPusher[0] and centerStart[1] > centerPusher[1]):
                    # Gehe sicher, dass der Pusher nicht über die Mittellinie hinaus geht
                    if centerStart[0] < 320:
                        ser.write(b"0\n")
                        print("Stop wegen Mittellinie")
                    elif centerStart[0] >= 320:
                        ser.write(b"2\n")
                        print("-xy")
                elif(centerStart[0] > centerPusher[0] and centerStart[1] < centerPusher[1]):
                    ser.write(b"3\n")
                    print("x-y")
                elif(centerStart[0] < centerPusher[0] and centerStart[1] < centerPusher[1]):
                    if centerStart[0] < 320:
                        ser.write(b"0\n")
                        print("Stop wegen Mittellinie")
                    elif centerStart[0] >= 320:
                        ser.write(b"4\n")
                        print("-x-y")
                elif(centerStart[0] == centerPusher[0] and centerStart[1] > centerPusher[1]):
                    ser.write(b"5\n")
                    print("0y")
                elif(centerStart[0] == centerPusher[0] and centerStart[1] < centerPusher[1]):
                    ser.write(b"6\n")
                    print("0-y")
                elif(centerStart[0] > centerPusher[0] and centerStart[1] == centerPusher[1]):
                    ser.write(b"7\n")
                    print("x0")
                elif(centerStart[0] < centerPusher[0] and centerStart[1] == centerPusher[1]):
                    if centerStart[0] < 320:
                        ser.write(b"0\n")
                        print("Stop wegen Mittellinie")
                    elif centerStart[0] >= 320:
                        ser.write(b"8\n")
                        print("-x0")
                # Pusher nochmal erfassen
                cntsP = cv2.findContours(maskBlue.copy(), cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE)
                cntsP = imutils.grab_contours(cntsP)
                centerPusher = None
                if len(cntsP) > 0:
                    # Finde die größte Kontur
                    # Berechne den Mittelpunkt 
                    cP = max(cntsP, key=cv2.contourArea)
                    MP = cv2.moments(cP)
                    centerPusher = (int(MP["m10"] / MP["m00"]), int(MP["m01"] / MP["m00"]))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    ser.write(b"0\n")
                    break
            ser.write(b"0\n")
            break
        if key == ord("q"):
            ser.write(b"0\n")
            break
# Speicherfreigabe
cap.release()
# close all windows
cv2.destroyAllWindows()
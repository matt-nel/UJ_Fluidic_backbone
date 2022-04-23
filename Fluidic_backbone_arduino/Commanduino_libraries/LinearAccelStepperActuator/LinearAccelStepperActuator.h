#ifndef LinearAccelStepperActuator_h
#define LinearAccelStepperActuator_h

#if defined(WIRING) && WIRING >= 100
  #include <Wiring.h>
#elif defined(ARDUINO) && ARDUINO >= 100
  #include <Arduino.h>
#else
  #include <WProgram.h>
#endif

#include <AccelStepper.h>

// Uncomment the next line to run the library in debug mode (verbose messages)
// #define LINEARACCELLSTEPPERACTUATOR_DEBUG

class LinearAccelStepperActuator {
  public:
    LinearAccelStepperActuator();
    LinearAccelStepperActuator(AccelStepper &mystepper, int myHomeSwitchPin, int myEnablePin, int* myEncoderCount);

    bool checkEncoder();
    void startMove();

    AccelStepper *stepper;
    int homeSwitchPin;
    int enablePin;

    void init();
    void home();
    void update();

    int* encoderCount;
    int reqEncoderCount;

    bool homeSwitchState();
    boolean isMoving();

    void move(long relativeSteps);
    void moveTo(long absoluteSteps);
    void stop();

    long distanceToGo();
    long targetPosition();
    long currentPosition();
    void setCurrentPosition(long position);

    void setSpeed(float stepsPerSecond);
    void setMaxSpeed(float stepsPerSecond);
    void setAcceleration(float stepsPerSecondPerSecond);

    float speed();
    float maxSpeed();
    float acceleration();

    void enableAcceleration();
    void disableAcceleration();

    void enableRevertedSwitch();
    void disableRevertedSwitch();

  private:

    bool homing;
    bool moving;
    bool accelerationEnabled;

    float lastSetSpeed;
    float lastSetAcceleration;
    bool accelerating;

    long curPos, startPos;

    int stepsPerRev = 3200;
    int numGaps = 8;
  
    boolean revertSwitchEnabled;
};

#endif

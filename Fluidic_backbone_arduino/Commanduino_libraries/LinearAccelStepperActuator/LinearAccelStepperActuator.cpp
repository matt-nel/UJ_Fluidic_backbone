#include "LinearAccelStepperActuator.h"

LinearAccelStepperActuator::LinearAccelStepperActuator() {

}

LinearAccelStepperActuator::LinearAccelStepperActuator(AccelStepper &mystepper, int myHomeSwitchPin, int myEnablePin, int* myEncoderCount) {
  
  encoderCount = myEncoderCount;

  homing = false;
  moving = false;

  stepper = &mystepper;
  
  int speed = 5000;
  setSpeed(speed);
  setMaxSpeed(speed);
  setAcceleration(2000);
  disableAcceleration();

  homeSwitchPin = myHomeSwitchPin;
  stepper->setEnablePin(myEnablePin);
  enablePin = myEnablePin;
  enableRevertedSwitch();
  stepper->setPinsInverted(false, false, true);
  stepper->disableOutputs();
}

void LinearAccelStepperActuator::init() {
  pinMode(homeSwitchPin, INPUT);
}

// you should set a speed first
// positive or negative depending on your setup and switch position
void LinearAccelStepperActuator::home() {
  homing = true;
  moving = true;
  move(50000);
}

void LinearAccelStepperActuator::update() {
  if (homing){
    if (homeSwitchState() == HIGH) {
      stop();
      setCurrentPosition(0);
    } else {
      stepper->runSpeedToPosition();
      checkEncoder();
    }
  } else {
    if (accelerationEnabled == true) {
      stepper->run();
      if (moving){
        checkEncoder();
      }
    } else {
      stepper->runSpeedToPosition();
      if (moving)
        checkEncoder(); 
    }
    if (distanceToGo() == 0) {
      moving = false;
      stepper->disableOutputs();
    }
  }
}

bool LinearAccelStepperActuator::homeSwitchState() {
  bool switchState = digitalRead(homeSwitchPin);
  if (revertSwitchEnabled) {
    switchState = !switchState;
  }
  return switchState;
}

bool LinearAccelStepperActuator::isMoving() {
  return moving;
}

bool LinearAccelStepperActuator::checkEncoder(){
  curPos = stepper->currentPosition();
  if (abs(curPos - startPos)>(stepsPerRev/numGaps)){
    startPos = curPos;
    reqEncoderCount ++;
    if (*encoderCount - reqEncoderCount < -3){
        stop();
    }
  }
}

void LinearAccelStepperActuator::move(long relativeSteps) {
  *encoderCount = 0;
  reqEncoderCount = 0;
  startPos = stepper->currentPosition();
  stepper->enableOutputs();
  stepper->move(relativeSteps);
  moving = true;
  // we must set the speed here, because by default accel stepper compute speed from acceleration, here we force it to go to speed, so we have to set back the speed after a move
  if (!accelerationEnabled) {
    setSpeed(lastSetSpeed);
  }
}

void LinearAccelStepperActuator::moveTo(long absoluteSteps) {
  *encoderCount = 0;
  reqEncoderCount = 0;
  startPos = stepper->currentPosition();
  stepper->enableOutputs();
  stepper->moveTo(absoluteSteps);
  moving = true;
  // we must set the speed here, because by default accel stepper compute speed from acceleration, here we force it to go to speed, so we have to set back the speed after a moveTo
  if (!accelerationEnabled) {
    setSpeed(lastSetSpeed);
  }
}

void LinearAccelStepperActuator::stop() {
  // the stop does not automatically set the current position to goal position because by default the accel stepper library is made to handle acceleration. Thus the servo by default slows down to stop at an undefined position
  // In speed mode, we want to stop immediately so we move(0) such that our goal position is now current position
  // we also stop homing
  // if in acceleration mode, the motor will slow down to complete stop, default behavior of AccelStepper
  homing = false;
  stepper->stop();
  if (!accelerationEnabled || homing) {
    stepper->move(0);
  }
}

long LinearAccelStepperActuator::distanceToGo() {
  return stepper->distanceToGo();
}

long LinearAccelStepperActuator::targetPosition() {
  return stepper->targetPosition();
}

long LinearAccelStepperActuator::currentPosition() {
  return stepper->currentPosition();
}

void LinearAccelStepperActuator::setCurrentPosition(long position) {
  stepper->setCurrentPosition(position);
}

void LinearAccelStepperActuator::setSpeed(float stepsPerSecond) {
  lastSetSpeed = stepsPerSecond;
  stepper->setSpeed(lastSetSpeed);
}

void LinearAccelStepperActuator::setMaxSpeed(float stepsPerSecond) {
  stepper->setMaxSpeed(stepsPerSecond);
}

void LinearAccelStepperActuator::setAcceleration(float stepsPerSecondPerSecond) {
  stepper->setAcceleration(stepsPerSecondPerSecond);
  lastSetAcceleration = stepsPerSecondPerSecond;
}

float LinearAccelStepperActuator::speed(){
  return stepper->speed();
}

float LinearAccelStepperActuator::maxSpeed(){
  return stepper->maxSpeed();
}

float LinearAccelStepperActuator::acceleration(){
  return stepper->acceleration();
}


void LinearAccelStepperActuator::enableAcceleration() {
  accelerationEnabled = true;
}

void LinearAccelStepperActuator::disableAcceleration() {
  accelerationEnabled = false;
}


void LinearAccelStepperActuator::enableRevertedSwitch() {
  revertSwitchEnabled = true;
}

void LinearAccelStepperActuator::disableRevertedSwitch() {
  revertSwitchEnabled = false;
}

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
extern "C" {
#include "deda.h"
}
#include "scenario_data.h"

Adafruit_SSD1306 display(128,64,&Wire,-1);
const uint8_t LED_PINS[]={18,19,21,4};
const uint8_t BUTTON_PINS[]={13,14,25,26,27};
const char *CLASS_NAMES[]={"Horn","Siren","Shout","Beep","Ambient"};
const char *CASE_NAMES[]={"HORN BEHIND","SIREN LEFT","NO DIRECTION","UNCERTAIN SOUND","AMBIENT ONLY"};
deda_state_t policy;
unsigned selected=0, frameIndex=0, alertCount=0;
unsigned long nextFrame=0, pulseStart=0, changedAt[5]={0};
bool playing=false, oledReady=false, rawPressed[5]={false}, stablePressed[5]={false};
uint8_t outputMask=0;
bool generalAlert=false;
float modelTime=0, alertDelay=0;
const char *stage="READY";
const char *detail="Select a button";

void showMask(uint8_t mask) {
 for(unsigned i=0;i<4;i++) digitalWrite(LED_PINS[i],(mask&(1u<<i))?HIGH:LOW);
}
void renderDisplay() {
 if(!oledReady) return;
 display.clearDisplay(); display.setTextSize(1);display.setTextColor(SSD1306_WHITE);
 display.setCursor(0,0);display.print("SOUNDSCAPE / DEDA");display.drawLine(0,10,127,10,SSD1306_WHITE);
 display.setCursor(0,14);display.print(CASE_NAMES[selected]);
 display.setCursor(0,25);display.print(stage);
 display.setCursor(0,36);display.print(detail);
 display.setCursor(0,47);
 if(alertCount) {display.print("Model delay: ");display.print((int)alertDelay);display.print("ms");}
 else {display.print("Model t: ");display.print((int)modelTime);display.print("ms");}
 display.setCursor(0,57);display.print("SIMULATED INPUTS");display.display();
}
void help() {
 Serial.println("SoundScape DEDA decision lab: synthetic inputs -> actual C policy -> LED commands");
 Serial.println("Buttons or serial 1-5 select cases. r=replay, c=clear, h=help.");
 Serial.println("64 ms model steps displayed every 650 ms. Printed delays are MODEL delays.");
 Serial.println("Directional: single pulses. General: double pulses. Patterns are illustrative.");
}
void startScenario(unsigned index) {
 selected=index;frameIndex=0;alertCount=0;outputMask=0;modelTime=0;alertDelay=0;
 deda_config_t cfg;deda_default_config(&cfg);deda_init(&policy,&cfg);
 playing=true;nextFrame=millis()+650;showMask(0);
 stage="PREPARED SCENARIO";detail="Awaiting onset";renderDisplay();
 Serial.printf("\nCASE %u: %s\n",selected+1,scenarios[selected].name);
}
void pollButtons() {
 unsigned long now=millis();
 for(unsigned i=0;i<5;i++) {
  bool pressed=digitalRead(BUTTON_PINS[i])==LOW;
  if(pressed!=rawPressed[i]) {rawPressed[i]=pressed;changedAt[i]=now;}
  if(now-changedAt[i]>=35 && stablePressed[i]!=rawPressed[i]) {
   stablePressed[i]=rawPressed[i];if(stablePressed[i]) startScenario(i);
  }
 }
}
void updatePulses() {
 // Repeating visual illustration; not a validated haptic encoding or repeated policy alerts.
 unsigned long phase=(millis()-pulseStart)%1200;
 bool on=generalAlert ? (phase<140 || (phase>=280 && phase<420)) : phase<260;
 showMask(on?outputMask:0);
}
void setup() {
 for(unsigned i=0;i<4;i++) pinMode(LED_PINS[i],OUTPUT);
 for(unsigned i=0;i<5;i++) pinMode(BUTTON_PINS[i],INPUT_PULLUP);
 Serial.begin(115200);Wire.begin(23,22);
 oledReady=display.begin(SSD1306_SWITCHCAPVCC,0x3c);
 if(!oledReady) Serial.println("OLED unavailable: serial and buttons remain usable.");
 help();startScenario(0);
}
void loop() {
 pollButtons();
 while(Serial.available()) {
  char ch=Serial.read();
  if(ch>='1' && ch<='5') startScenario(ch-'1');
  else if(ch=='r'||ch=='R') startScenario(selected);
  else if(ch=='h'||ch=='H') help();
  else if(ch=='c'||ch=='C') {playing=false;outputMask=0;alertCount=0;stage="CLEARED";detail="Select a button";renderDisplay();}
 }
 updatePulses();
 if(!playing || (long)(millis()-nextFrame)<0) return;
 nextFrame=millis()+650;
 const Scenario &scene=scenarios[selected];const deda_window_t &w=scene.windows[frameIndex++];
 modelTime=w.t_ms;
 deda_alert_t alerts[DEDA_MAX_ALERTS_PER_STEP];int count=deda_step(&policy,&w,alerts);
 if(!alertCount) {
  if(policy.latched>=0) {stage="CLASS ACCEPTED";detail="Waiting direction";}
  else if(policy.open) {stage="GATHERING EVIDENCE";detail=w.has_dir?"Checking direction":"Direction missing";}
  else {stage="NO ACCEPTED EVENT";detail=modelTime<=scene.onset_ms?"Awaiting onset":"Class not accepted";}
 }
 Serial.printf("model t=%.0f ms | direction=%s | class evidence %.2f %.2f %.2f %.2f\n",(double)w.t_ms,w.has_dir?"available":"missing",(double)policy.L[0],(double)policy.L[1],(double)policy.L[2],(double)policy.L[3]);
 for(int i=0;i<count;i++) {
  const deda_alert_t &a=alerts[i];outputMask=a.motors;generalAlert=a.kind==DEDA_ALERT_NONDIR;
  pulseStart=millis();alertCount++;alertDelay=a.t_ms-scene.onset_ms;
  stage=generalAlert?"GENERAL WARNING":"DIRECTIONAL ALERT";
  detail=generalAlert?"All four outputs":a.motors==1?"FRONT output":a.motors==2?"RIGHT output":a.motors==4?"BACK output":a.motors==8?"LEFT output":"Adjacent outputs";
  Serial.printf("ALERT: %s | class=%s | mask=%u | MODEL onset-to-command=%.0f ms\n",stage,CLASS_NAMES[a.cls],a.motors,(double)alertDelay);
 }
 if(frameIndex==scene.count) {
  playing=false;
  if(!alertCount) {stage="NO ALERT";detail=selected==4?"Ambient input only":"Class not accepted";}
  Serial.printf("Complete: %u alert(s). Result and illustrative pulses retained. Select 1-5.\n",alertCount);
 }
 renderDisplay();
}

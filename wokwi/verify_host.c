#include <stdio.h>
#include "sketch/scenario_data.h"
int main(void) {
 for(unsigned s=0;s<SCENARIO_COUNT;s++) {
  deda_config_t cfg; deda_default_config(&cfg); deda_state_t state; deda_init(&state,&cfg);
  for(unsigned i=0;i<scenarios[s].count;i++) {
   deda_alert_t alerts[DEDA_MAX_ALERTS_PER_STEP]; int n=deda_step(&state,&scenarios[s].windows[i],alerts);
   for(int a=0;a<n;a++) printf("%u,%.0f,%u,%u,%u\n",s,alerts[a].t_ms,alerts[a].kind,alerts[a].cls,alerts[a].motors);
  }
 }
 return 0;
}

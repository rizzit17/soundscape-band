import json
from pathlib import Path
parts=[dict(type='wokwi-esp32-devkit-v1',id='esp',top=20,left=-270,attrs={}),dict(type='board-ssd1306',id='oled',top=-110,left=-265,attrs=dict(i2cAddress='0x3c'))]
connections=[['esp:TX0','$serialMonitor:RX','',[]],['esp:RX0','$serialMonitor:TX','',[]],['oled:SDA','esp:D23','blue',[]],['oled:SCL','esp:D22','yellow',[]],['oled:VCC','esp:3V3','red',[]],['oled:GND','esp:GND.2','black',[]]]
for name,pin,color,x,y in [('Front',18,'green',100,-100),('Right',19,'blue',250,20),('Back',21,'red',100,150),('Left',4,'orange',-40,20)]:
 id=name.lower();parts += [dict(type='wokwi-led',id=id,top=y,left=x,attrs=dict(color=color,label=name+' motor')),dict(type='wokwi-resistor',id='r_'+id,top=y+50,left=x,attrs=dict(value='330'))]
 connections += [[f'esp:D{pin}',f'r_{id}:1',color,[]],[f'r_{id}:2',f'{id}:A',color,[]],[f'{id}:C','esp:GND.1','black',[]]]
for i,(label,pin,color) in enumerate([('1 HORN',13,'green'),('2 SIREN',14,'blue'),('3 NO DIRECTION',25,'yellow'),('4 UNCERTAIN',26,'orange'),('5 AMBIENT',27,'gray')]):
 id=f'btn{i}';parts.append(dict(type='wokwi-pushbutton',id=id,top=300,left=-260+i*145,attrs=dict(color=color,label=label,key=str(i+1))))
 connections += [[id+':1.l',f'esp:D{pin}','purple',[]],[id+':2.l','esp:GND.2','black',[]]]
for id,text,x,y in [('title','SOUNDSCAPE | DEDA DECISION LAB',-260,-190),('wearer','WEARER',90,50),('caption','Prepared synthetic inputs | LEDs represent vibration commands',-260,420),('controls','SELECT A SCENARIO BELOW',-260,255)]:
 parts.append(dict(type='wokwi-text',id=id,top=y,left=x,attrs=dict(text=text)))
Path('wokwi/sketch/diagram.json').write_text(json.dumps(dict(version=1,author='SoundScape team',editor='wokwi',parts=parts,connections=connections,serialMonitor=dict(display='always',newline='lf')),indent=2))

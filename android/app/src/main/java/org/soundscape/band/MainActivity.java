package org.soundscape.band;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.AudioFormat;
import android.media.AudioAttributes;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.os.Build;
import android.os.SystemClock;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.os.VibrationAttributes;
import android.provider.Settings;
import android.view.View;
import android.widget.*;
import com.google.mediapipe.tasks.audio.audioclassifier.AudioClassifier;
import com.google.mediapipe.tasks.audio.core.RunningMode;
import com.google.mediapipe.tasks.components.containers.AudioData;
import com.google.mediapipe.tasks.components.containers.Category;
import com.google.mediapipe.tasks.core.BaseOptions;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class MainActivity extends Activity {
    private static final int GREEN = Color.rgb(25,84,64), INK = Color.rgb(25,40,35);
    private TextView status, detection, details, top, counts, thresholdLabel;
    private Button start, stop, export, correct, incorrect;
    private Spinner expected;
    private SeekBar sensitivity;
    private Switch haptics, confirmSound;
    private TextView alertState, vibrationStatus;
    private volatile boolean running;
    private volatile AudioRecord recorder;
    private volatile boolean vibration = true;
    private long latestId;
    private int windows, matching, alerts;
    private File logFile;
    private final Object logLock = new Object();
    private String session;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        logFile = new File(getFilesDir(), "soundscape-tests.csv");
        ScrollView scroll = new ScrollView(this);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 48, 24, 32); layout.setBackgroundColor(Color.rgb(245,247,240));
        scroll.addView(layout); setContentView(scroll);
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(24, Math.max(24,insets.getSystemWindowInsetTop()),24,Math.max(24,insets.getSystemWindowInsetBottom())); return insets;
        });
        addText(layout,"SOUNDSCAPE / FIELD LAB",14,GREEN);
        addText(layout,"Hear the environment.\nFeel the alert.",30,INK);
        addText(layout,"Offline research prototype · YAMNet\nReal microphone input. No audio recordings saved.",14,INK);
        status = addText(layout,"Ready — choose an expected sound, then listen.",16,GREEN);
        status.setId(R.id.listen_status);
        detection = addText(layout,"Waiting for sound",28,INK);
        details = addText(layout,"Direction: unavailable on this prototype",14,INK);
        top = addText(layout,"Top model labels will appear here.",15,INK);
        alertState = addText(layout,"Alerts are for horns, sirens, reversing beeps and shouting.",15,GREEN);
        vibrationStatus = addText(layout,"Vibration: " + (phoneVibrator()!=null && phoneVibrator().hasVibrator() ? "motor available — tap Test vibration" : "no vibration motor available"),14,INK);
        vibrationStatus.setId(R.id.vibration_status);
        Button motorTest = button(layout,"Test vibration (no sound needed)",v -> {
            boolean sent = vibrate(1);
            if(sent) vibrationStatus.setText("Test vibration requested. If you felt nothing, check phone vibration intensity and Do Not Disturb in Sound settings.");
        });
        motorTest.setId(R.id.vibration_test);
        button(layout,"Open phone sound settings",v -> {
            try { startActivity(new Intent(Settings.ACTION_SOUND_SETTINGS)); }
            catch(android.content.ActivityNotFoundException e) { vibrationStatus.setText("Open your phone's Sound & vibration settings manually."); }
        });
        addText(layout,"Expected sound for this session",16,INK);
        expected = new Spinner(this);
        String[] options = {"Unlabelled exploration", "Horn", "Siren", "Reversing beeps", "Shouting", "Other / uncertain"};
        expected.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,options)); layout.addView(expected);
        thresholdLabel = addText(layout,"Detection threshold: 0.30",16,INK);
        sensitivity = new SeekBar(this); sensitivity.setMax(80); sensitivity.setProgress(20); layout.addView(sensitivity);
        sensitivity.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar b,int p,boolean user) { thresholdLabel.setText(String.format(Locale.US,"Detection threshold: %.2f",(p+10)/100f)); }
            public void onStartTrackingTouch(SeekBar b) {} public void onStopTrackingTouch(SeekBar b) {}
        });
        haptics = new Switch(this); haptics.setText("Vibration alerts"); haptics.setChecked(true); layout.addView(haptics);
        haptics.setOnCheckedChangeListener((b,checked) -> vibration = checked);
        confirmSound = new Switch(this); confirmSound.setText("Require two matching windows (slower, fewer brief alerts)");
        confirmSound.setChecked(false); layout.addView(confirmSound);
        start = button(layout,"Start listening",v -> begin());
        start.setId(R.id.listen_start);
        stop = button(layout,"Stop listening",v -> stopListening()); stop.setEnabled(false);
        stop.setId(R.id.listen_stop);
        correct = button(layout,"Mark latest result correct",v -> feedback("correct"));
        incorrect = button(layout,"Mark latest result incorrect",v -> feedback("incorrect"));
        correct.setEnabled(false); incorrect.setEnabled(false);
        counts = addText(layout,"Session: 0 windows · 0 alerts",15,INK);
        export = button(layout,"Export all test results (CSV)",v -> {
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("text/csv").addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,"SoundScape-tests.csv"); startActivityForResult(intent,20);
        });
        addText(layout,"How to test",21,INK);
        addText(layout,"1. Choose the sound you will play from another device.\n2. Start listening and play 10–15 seconds at a comfortable volume.\n3. Stop, then repeat with other sounds and ordinary background noise.\n4. Export the CSV for your project evaluation.",15,INK);
        addText(layout,"What this validates",21,INK);
        addText(layout,"Sound recognition and phone vibration only. Each window contains 975 ms of mono audio. By default, one qualifying window requests an alert, followed by a 3-second cooldown. Enable two-window confirmation for more persistence. Other model labels can appear without triggering these four target alerts. Scores are model scores, not calibrated probabilities. This is a separate phone policy, not directional DEDA.\n\nHorn: two pulses · Siren: one long pulse · Reversing beeps: three short pulses · Shouting: short–long. Android sound settings and Do Not Disturb can suppress vibration; the app reports requests, not confirmation that the motor moved.\n\nThe app stops listening when you leave it. It does not measure source angle, four-motor feedback, or the band's 300 ms target. Do not rely on this prototype as a safety alarm.",14,INK);
    }
    private TextView addText(LinearLayout parent,String text,int size,int color) {
        TextView t = new TextView(this); t.setText(text); t.setTextSize(size); t.setTextColor(color); t.setPadding(0,12,0,12); parent.addView(t); return t;
    }
    private Button button(LinearLayout parent,String text,View.OnClickListener action) {
        Button b = new Button(this); b.setText(text); b.setAllCaps(false); b.setTextColor(GREEN); parent.addView(b); b.setOnClickListener(action); return b;
    }
    private void begin() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},10); return; }
        if (running || !start.isEnabled()) return;
        final float threshold = (sensitivity.getProgress()+10)/100f;
        final int truth = expected.getSelectedItemPosition()-1;
        final int requiredWindows = confirmSound.isChecked() ? 2 : 1;
        running = true; windows=0; matching=0; alerts=0; latestId=0;
        session=UUID.randomUUID().toString();
        start.setEnabled(false); stop.setEnabled(true); sensitivity.setEnabled(false); expected.setEnabled(false); export.setEnabled(false);
        confirmSound.setEnabled(false);
        correct.setEnabled(false); incorrect.setEnabled(false);
        status.setText("Loading offline model…");
        new Thread(() -> listen(threshold,truth,requiredWindows),"SoundScape-audio").start();
    }
    private void listen(float threshold,int truth,int requiredWindows) {
        AudioClassifier classifier=null; AudioRecord local=null;
        String failure=null;
        try {
            classifier=AudioClassifier.createFromOptions(this,AudioClassifier.AudioClassifierOptions.builder()
                .setBaseOptions(BaseOptions.builder().setModelAssetPath("yamnet.tflite").build())
                .setRunningMode(RunningMode.AUDIO_CLIPS).setMaxResults(521).build());
            int minimum=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_FLOAT);
            if(minimum <= 0) throw new IOException("16 kHz float audio input is unavailable");
            if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) throw new SecurityException("Microphone permission was revoked");
            local=new AudioRecord.Builder().setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
                .setAudioFormat(new AudioFormat.Builder().setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_IN_MONO).setEncoding(AudioFormat.ENCODING_PCM_FLOAT).build())
                .setBufferSizeInBytes(Math.max(minimum,15600*4*4)).build();
            recorder=local;
            if (!running) return;
            local.startRecording();
            AudioData data=AudioData.create(AudioData.AudioDataFormat.builder().setNumOfChannels(1).setSampleRate(16000).build(),15600);
            AlertPolicy policy=new AlertPolicy(requiredWindows); float[] samples=new float[15600];
            append("config,"+session+","+System.currentTimeMillis()+",,,,,,,,,app=0.2;required_windows="+requiredWindows+";cooldown_ms=3000\n");
            long started=SystemClock.elapsedRealtime();
            while(running) {
                int filled=0;
                while(running && filled<samples.length) {
                    int n=local.read(samples,filled,samples.length-filled,AudioRecord.READ_BLOCKING);
                    if(n<=0) { if(!running) break; throw new IOException("Microphone read failed: "+n); } filled+=n;
                }
                if(!running) break;
                double energy=0; for(float s:samples) energy+=s*s;
                final double db=20*Math.log10(Math.max(1e-8,Math.sqrt(energy/samples.length)));
                data.load(samples); long before=SystemClock.elapsedRealtime();
                var result=classifier.classify(data); long inference=SystemClock.elapsedRealtime()-before;
                List<Category> categories=new ArrayList<>(result.classificationResults().get(0).classifications().get(0).categories());
                categories.sort((a,b)->Float.compare(b.score(),a.score()));
                float[] scores=new float[4];
                for(Category c:categories) { int g=AlertPolicy.group(c.index()); if(g<4) scores[g]=Math.max(scores[g],c.score()); }
                int best=0; for(int i=1;i<4;i++) if(scores[i]>scores[best]) best=i;
                float score=scores[best]; int detected=score>=threshold?best:4;
                long elapsed=SystemClock.elapsedRealtime()-started;
                boolean alert=policy.update(detected,score,threshold,elapsed);
                final String alertMessage=policy.status();
                StringBuilder labels=new StringBuilder();
                for(int i=0;i<Math.min(5,categories.size());i++) { Category c=categories.get(i); labels.append(String.format(Locale.US,"%s  %.2f\n",c.categoryName(),c.score())); }
                final String labelText=labels.toString(); final int group=detected;
                final long id=System.currentTimeMillis();
                append(String.format(Locale.US,"window,%s,%d,%d,%s,%s,%.4f,%.2f,%b,%d,%.1f,\n",session,id,elapsed,truth<0?"unlabelled":AlertPolicy.GROUPS[truth],AlertPolicy.GROUPS[group],score,threshold,alert,inference,db));
                runOnUiThread(() -> {
                    if(!running) return;
                    latestId=id; windows++; if(truth==group) matching++; if(alert) alerts++;
                    status.setText("Listening · offline · microphone active");
                    detection.setText(AlertPolicy.GROUPS[group]);
                    details.setText(String.format(Locale.US,"Target score %.2f · inference %d ms\nInput %.0f dBFS · direction unavailable",score,inference,db));
                    top.setText(labelText); correct.setEnabled(true); incorrect.setEnabled(true);
                    alertState.setText(alertMessage + (vibration ? "" : " · vibration switch is off"));
                    counts.setText("Session: "+windows+" windows · "+alerts+" alerts"+(truth<0?"":"\nExpected-class matches: "+matching+"/"+windows+" (window-level)"));
                    if(alert && vibration) vibrate(group);
                });
            }
        } catch(Exception | LinkageError e) { if(running) failure=e.getClass().getSimpleName()+": "+e.getMessage(); }
        finally {
            running=false; recorder=null;
            if(local!=null) { try { local.stop(); } catch(Exception ignored) {} local.release(); }
            if(classifier!=null) classifier.close();
            final String message=failure;
            runOnUiThread(() -> { start.setEnabled(true); stop.setEnabled(false); sensitivity.setEnabled(true); expected.setEnabled(true); export.setEnabled(true); confirmSound.setEnabled(true); status.setText(message==null?"Stopped · microphone off":"Could not listen: "+message); });
        }
    }
    private void stopListening() {
        running=false; AudioRecord r=recorder;
        if(r!=null) try { r.stop(); } catch(Exception ignored) {}
        Vibrator motor=phoneVibrator(); if(motor!=null) motor.cancel();
    }
    private Vibrator phoneVibrator() {
        if(Build.VERSION.SDK_INT>=31) {
            VibratorManager manager=getSystemService(VibratorManager.class);
            if(manager!=null) return manager.getDefaultVibrator();
        }
        return (Vibrator)getSystemService(VIBRATOR_SERVICE);
    }
    private boolean vibrate(int group) {
        Vibrator motor=phoneVibrator();
        if(motor==null || !motor.hasVibrator()) { vibrationStatus.setText("No vibration motor is available on this device."); return false; }
        long[][] patterns={{0,300,160,300},{0,800},{0,180,120,180,120,180},{0,180,150,500}};
        long[] timing=patterns[group]; int[] amplitudes=new int[timing.length];
        for(int i=1;i<amplitudes.length;i+=2) amplitudes[i]=255;
        try {
            VibrationEffect effect=VibrationEffect.createWaveform(timing,amplitudes,-1);
            if(Build.VERSION.SDK_INT>=33) motor.vibrate(effect,new VibrationAttributes.Builder().setUsage(VibrationAttributes.USAGE_NOTIFICATION).build());
            else motor.vibrate(effect,new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            NotificationManager notifications=getSystemService(NotificationManager.class);
            boolean dnd=notifications!=null && notifications.getCurrentInterruptionFilter()!=NotificationManager.INTERRUPTION_FILTER_ALL;
            vibrationStatus.setText("Vibration requested: "+AlertPolicy.GROUPS[group]+(dnd?" · Do Not Disturb may suppress it":" · check phone settings if you feel nothing"));
            return true;
        } catch(RuntimeException e) { vibrationStatus.setText("Vibration request failed: "+e.getMessage()); return false; }
    }
    private void append(String row) throws IOException {
        synchronized(logLock) {
            boolean fresh=!logFile.exists() || logFile.length()==0;
            try(FileOutputStream out=new FileOutputStream(logFile,true)) {
                if(fresh) out.write("kind,session,id_utc_ms,session_elapsed_ms,expected,detected,target_score,threshold,alert,inference_ms,input_dbfs,feedback\n".getBytes(StandardCharsets.UTF_8));
                out.write(row.getBytes(StandardCharsets.UTF_8));
            }
        }
    }
    private void feedback(String assessment) {
        if(latestId==0) return;
        try { append("feedback,"+session+","+latestId+",,,,,,,,,"+assessment+"\n"); Toast.makeText(this,"Saved feedback",Toast.LENGTH_SHORT).show(); }
        catch(IOException e) { status.setText("Could not save feedback: "+e.getMessage()); }
    }
    @Override protected void onPause() { super.onPause(); stopListening(); }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==10 && results.length>0 && results[0]==PackageManager.PERMISSION_GRANTED) begin();
        else status.setText("Microphone permission is needed to classify real sounds. Tap Start to retry.");
    }
    @Override protected void onActivityResult(int request,int result,Intent intent) {
        super.onActivityResult(request,result,intent);
        if(request==20 && result==RESULT_OK && intent!=null && intent.getData()!=null) {
            try(OutputStream out=getContentResolver().openOutputStream(intent.getData())) {
                if(out==null) throw new IOException("No output stream");
                synchronized(logLock) { try(InputStream in=new FileInputStream(logFile)) { byte[] buffer=new byte[8192]; int n; while((n=in.read(buffer))!=-1) out.write(buffer,0,n); } }
                status.setText("Test results exported.");
            } catch(IOException e) { status.setText("Export failed: "+e.getMessage()); }
        }
    }
}

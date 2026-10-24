package org.soundscape.band;
import android.Manifest;
import android.content.Intent;
import android.widget.TextView;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class MicrophoneTest {
    @Test public void liveCaptureProducesLogAndStopsWhenActivityCloses() throws Exception {
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        var context=instrumentation.getTargetContext();
        instrumentation.getUiAutomation().grantRuntimePermission(context.getPackageName(),Manifest.permission.RECORD_AUDIO);
        var activity=(MainActivity)instrumentation.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try {
            instrumentation.runOnMainSync(()->activity.findViewById(R.id.listen_start).performClick());
            AtomicReference<String> status=new AtomicReference<>("");
            long deadline=System.currentTimeMillis()+40000;
            do {
                Thread.sleep(250);
                instrumentation.runOnMainSync(()->status.set(((TextView)activity.findViewById(R.id.listen_status)).getText().toString()));
            } while(!status.get().startsWith("Listening") && !status.get().startsWith("Could not") && System.currentTimeMillis()<deadline);
            assertTrue(status.get(),status.get().startsWith("Listening"));
            File log=new File(context.getFilesDir(),"soundscape-tests.csv");
            assertTrue("Live capture must save classified windows",log.length()>150);
            instrumentation.runOnMainSync(activity::finish);
            Thread.sleep(1500);
            long stoppedLength=log.length(); Thread.sleep(1500);
            assertEquals("Capture must stop when the activity leaves foreground",stoppedLength,log.length());
        } finally { instrumentation.runOnMainSync(activity::finish); }
    }
}

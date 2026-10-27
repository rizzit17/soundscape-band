package org.soundscape.band;
import android.content.Intent;
import android.widget.TextView;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class VibrationTest {
    @Test public void manualMotorCheckDoesNotRequireMicrophonePermission() {
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        var context=instrumentation.getTargetContext();
        var activity=(MainActivity)instrumentation.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        try {
            instrumentation.runOnMainSync(()-> {
                activity.findViewById(R.id.vibration_test).performClick();
                String status=((TextView)activity.findViewById(R.id.vibration_status)).getText().toString();
                assertTrue(status,status.startsWith("Test vibration requested") || status.startsWith("No vibration motor"));
                assertTrue(activity.findViewById(R.id.listen_start).isEnabled());
            });
        } finally { instrumentation.runOnMainSync(activity::finish); }
    }
}

package org.soundscape.band;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.google.mediapipe.tasks.audio.audioclassifier.AudioClassifier;
import com.google.mediapipe.tasks.audio.core.RunningMode;
import com.google.mediapipe.tasks.components.containers.AudioData;
import com.google.mediapipe.tasks.core.BaseOptions;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class ModelTest {
    @Test public void bundledModelRecognizesSilenceAndHasExpectedClasses() {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        try(var model=AudioClassifier.createFromOptions(context,AudioClassifier.AudioClassifierOptions.builder()
            .setBaseOptions(BaseOptions.builder().setModelAssetPath("yamnet.tflite").build())
            .setRunningMode(RunningMode.AUDIO_CLIPS).setMaxResults(521).build())) {
            var data=AudioData.create(AudioData.AudioDataFormat.builder().setNumOfChannels(1).setSampleRate(16000).build(),15600);
            data.load(new float[15600]);
            var categories=model.classify(data).classificationResults().get(0).classifications().get(0).categories();
            assertEquals(521,categories.size());
            assertEquals("Silence",categories.get(0).categoryName());
            assertTrue(categories.get(0).score()>.5f);
            assertTrue(categories.stream().anyMatch(c->c.index()==313 && c.categoryName().equals("Reversing beeps")));
            assertTrue(categories.stream().anyMatch(c->c.index()==302 && c.categoryName().equals("Vehicle horn, car horn, honking")));
        }
    }
}

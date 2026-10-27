package org.soundscape.band;
import org.junit.Test;
import static org.junit.Assert.*;
public class AlertPolicyTest {
    @Test public void quickModeAlertsOnOneWindowButStillHasCooldown() {
        AlertPolicy p = new AlertPolicy(1);
        assertTrue(p.update(0,.8f,.3f,0)); assertFalse(p.update(1,.8f,.3f,1000));
        assertTrue(p.status().contains("cooldown")); assertTrue(p.update(1,.8f,.3f,3000));
    }
    @Test public void invalidOrLowConfidenceSoundCannotVibrate() {
        AlertPolicy p = new AlertPolicy(1);
        assertFalse(p.update(4,.9f,.3f,0)); assertFalse(p.update(0,.2f,.3f,1000));
        assertFalse(p.update(0,Float.NaN,.3f,2000));
    }
    @Test public void beepIsNotAutomaticallyReversing() { assertEquals(4, AlertPolicy.group(475)); assertEquals(2, AlertPolicy.group(313)); }
    @Test public void persistenceAndCooldown() {
        AlertPolicy p = new AlertPolicy();
        assertFalse(p.update(0,.8f,.3f,0)); assertTrue(p.update(0,.8f,.3f,1000));
        assertFalse(p.update(0,.8f,.3f,2000)); assertTrue(p.update(0,.8f,.3f,4000));
    }
    @Test public void uncertaintyResetsEvidence() {
        AlertPolicy p = new AlertPolicy(); p.update(1,.8f,.3f,0);
        assertFalse(p.update(1,.1f,.3f,1000)); assertFalse(p.update(1,.8f,.3f,2000));
        assertFalse(p.update(4,.9f,.3f,3000));
    }
    @Test public void changedClassNeedsNewEvidence() {
        AlertPolicy p = new AlertPolicy(); p.update(0,.8f,.3f,0);
        assertFalse(p.update(1,.8f,.3f,1000)); assertTrue(p.update(1,.8f,.3f,2000));
    }
}

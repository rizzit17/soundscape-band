package org.soundscape.band;

/** Phone-only persistence gate; does not implement the array's directional DEDA. */
public final class AlertPolicy {
    public static final String[] GROUPS = {"Horn", "Siren", "Reversing beeps", "Shouting", "Other / uncertain"};
    private int previous = -1, consecutive = 0;
    private long lastAlert = -10000;
    private final int requiredWindows;
    private String status = "Waiting for a target sound";
    public AlertPolicy() { this(2); }
    public AlertPolicy(int requiredWindows) {
        if (requiredWindows < 1 || requiredWindows > 2) throw new IllegalArgumentException("Use one or two windows");
        this.requiredWindows = requiredWindows;
    }
    public String status() { return status; }
    public static int group(int index) {
        return switch (index) {
            case 302, 303, 312, 325 -> 0;
            case 317, 318, 319, 390, 391 -> 1;
            case 313 -> 2;
            case 6, 7, 8, 9, 10, 11 -> 3;
            default -> 4;
        };
    }
    public boolean update(int group, float score, float threshold, long now) {
        if (group < 0 || group >= 4 || !Float.isFinite(score) || score < threshold) {
            previous = -1; consecutive = 0; status = "Waiting for a target sound above threshold"; return false;
        }
        consecutive = previous == group ? consecutive + 1 : 1;
        previous = group;
        if (consecutive < requiredWindows) { status = "Confirming sound: " + consecutive + "/" + requiredWindows + " windows"; return false; }
        long remaining = 3000 - (now - lastAlert);
        if (remaining > 0) { status = "Alert cooldown: " + ((remaining + 999) / 1000) + " s remaining"; return false; }
        lastAlert = now;
        status = "Alert triggered: " + GROUPS[group];
        return true;
    }
}

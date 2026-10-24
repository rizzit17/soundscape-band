package org.soundscape.band;

/** Phone-only persistence gate; does not implement the array's directional DEDA. */
public final class AlertPolicy {
    public static final String[] GROUPS = {"Horn", "Siren", "Reversing beeps", "Shouting", "Other / uncertain"};
    private int previous = -1, consecutive = 0;
    private long lastAlert = -10000;
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
        if (group == 4 || score < threshold) { previous = -1; consecutive = 0; return false; }
        consecutive = previous == group ? consecutive + 1 : 1;
        previous = group;
        if (consecutive >= 2 && now - lastAlert >= 3000) { lastAlert = now; return true; }
        return false;
    }
}

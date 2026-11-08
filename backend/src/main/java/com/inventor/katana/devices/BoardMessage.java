package com.inventor.katana.devices;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.List;

/** Validate the whole frame before a transactional sink changes any state. */
public record BoardMessage(JsonNode body) {
    public static BoardMessage parse(ObjectMapper mapper, String line) throws IOException {
        JsonNode body = mapper.readTree(line);
        require(body != null && body.isObject(), "object_required");
        require(body.has("cfg") || body.has("st") || body.has("logs") || body.has("log") || body.has("m"), "unknown_frame");
        if (body.has("cfg")) {
            object(body.get("cfg"));
            JsonNode systems = body.get("cfg").get("cor");
            if (systems != null) {
                array(systems, 256);
                for (JsonNode system : systems) text(system, 200);
            }
        }
        if (body.has("st")) {
            JsonNode state = body.get("st"); object(state);
            if (state.has("pue")) {
                text(state.get("pue"), 1);
                require(List.of("A", "B").contains(state.get("pue").asText().toUpperCase(java.util.Locale.ROOT)), "invalid_door");
            }
            if (state.hasNonNull("puerta")) text(state.get("puerta"), 100);
            if (state.hasNonNull("up")) require(state.get("up").isIntegralNumber() && state.get("up").asLong() >= 0, "invalid_uptime");
            if (state.hasNonNull("el")) {
                array(state.get("el"), 3);
                require(state.get("el").size() == 3, "three_elements_required");
                for (JsonNode element : state.get("el")) require(element.isIntegralNumber() && (element.asInt() == 0 || element.asInt() == 1), "invalid_element");
            }
            if (state.has("al")) {
                array(state.get("al"), 512);
                for (JsonNode alarm : state.get("al")) {
                    tuple(alarm, 5); require(alarm.get(0).isIntegralNumber() && alarm.get(0).asInt() >= 0, "invalid_system_index");
                    severity(alarm.get(1));
                    require(alarm.get(2).isBoolean() || (alarm.get(2).isIntegralNumber() && (alarm.get(2).asInt() == 0 || alarm.get(2).asInt() == 1)), "invalid_ack");
                    timestamp(alarm.get(3)); text(alarm.get(4), 8192);
                }
            }
        }
        if (body.has("logs")) {
            array(body.get("logs"), 512);
            for (JsonNode log : body.get("logs")) {
                tuple(log, 4); timestamp(log.get(0)); severity(log.get(1)); text(log.get(2), 200); text(log.get(3), 8192);
            }
        }
        if (body.has("log")) {
            JsonNode log = body.get("log"); object(log);
            timestamp(log.get("t")); severity(log.get("v")); text(log.get("s"), 200); text(log.get("m"), 8192);
        }
        if (body.has("m")) {
            array(body.get("m"), 512);
            for (JsonNode sample : body.get("m")) {
                tuple(sample, 4); text(sample.get(0), 200); text(sample.get(1), 200);
                require(sample.get(2).isNumber() && Double.isFinite(sample.get(2).asDouble()), "invalid_value");
                text(sample.get(3), 100);
            }
        }
        return new BoardMessage(body.deepCopy());
    }
    private static void timestamp(JsonNode n) { require(n != null && n.isNumber() && Double.isFinite(n.asDouble()) && n.asDouble() >= 0, "invalid_timestamp"); }
    private static void severity(JsonNode n) { require(n != null && n.isIntegralNumber() && n.asInt() >= 0 && n.asInt() <= 3, "invalid_severity"); }
    private static void text(JsonNode n, int max) { require(n != null && n.isTextual() && n.asText().length() <= max, "invalid_text"); }
    private static void object(JsonNode n) { require(n != null && n.isObject(), "object_required"); }
    private static void array(JsonNode n, int max) { require(n != null && n.isArray() && n.size() <= max, "invalid_array"); }
    private static void tuple(JsonNode n, int size) { array(n, size); require(n.size() == size, "invalid_tuple"); }
    private static void require(boolean value, String reason) { if (!value) throw new IllegalArgumentException(reason); }
}

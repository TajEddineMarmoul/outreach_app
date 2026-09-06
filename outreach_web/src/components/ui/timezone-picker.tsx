"use client";

import { useMemo, useState } from "react";
import { Combobox } from "@base-ui/react/combobox";
import { Check, ChevronDown } from "lucide-react";
import { supportedTimeZones, timeZoneOption } from "@/lib/timezones";
import styles from "./timezone-picker.module.css";

type TimeZoneOption = ReturnType<typeof timeZoneOption>;

function matchesTimeZone(option: TimeZoneOption, query: string) {
  const searchable = `${option.label} ${option.value}`.replaceAll("_", " ").toLowerCase();
  return query.trim().replaceAll("_", " ").toLowerCase().split(/\s+/)
    .every((word) => searchable.includes(word));
}

export function TimeZonePicker({ id, value, onChange, disabled = false }: {
  id: string;
  value: string;
  onChange: (timeZone: string) => void;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const options = useMemo(() => {
    const now = new Date();
    return Array.from(new Set([value, ...supportedTimeZones()]))
      .map((zone) => timeZoneOption(zone, now))
      .sort((left, right) => left.city.localeCompare(right.city) || left.value.localeCompare(right.value));
  }, [value]);
  const rankedOptions = useMemo(() => {
    const prefix = query.trim().replaceAll("_", " ").toLowerCase();
    if (!prefix) return options;
    return [...options].sort((left, right) =>
      Number(right.city.toLowerCase().startsWith(prefix)) - Number(left.city.toLowerCase().startsWith(prefix)),
    );
  }, [options, query]);
  const selected = options.find((option) => option.value === value) || null;

  return (
    <Combobox.Root
      items={rankedOptions}
      value={selected}
      onInputValueChange={setQuery}
      onValueChange={(option) => { if (option) onChange(option.value); }}
      isItemEqualToValue={(option, selection) => option.value === selection.value}
      filter={matchesTimeZone}
      autoHighlight
      disabled={disabled}
    >
      <Combobox.InputGroup className={styles.control}>
        <Combobox.Input
          id={id}
          className={styles.input}
          style={{ paddingRight: 44 }}
          placeholder="Search city or timezone…"
          aria-describedby={`${id}-hint`}
          onFocus={(event) => event.currentTarget.select()}
        />
        <Combobox.Trigger className={styles.trigger} aria-label="Show timezones">
          <ChevronDown size={16} aria-hidden="true" />
        </Combobox.Trigger>
      </Combobox.InputGroup>
      <p id={`${id}-hint`} className={styles.hint}>Type a city or timezone to search.</p>
      <Combobox.Portal>
        <Combobox.Positioner sideOffset={6} align="start" className={styles.positioner}>
          <Combobox.Popup className={styles.popup}>
            <Combobox.Empty className={styles.empty}>No timezones found. Try another city or UTC offset.</Combobox.Empty>
            <Combobox.List className={styles.list}>
              {(option: TimeZoneOption) => (
                <Combobox.Item key={option.value} value={option} className={styles.option}>
                  <span className={styles.indicator}>
                    <Combobox.ItemIndicator><Check size={16} aria-hidden="true" /></Combobox.ItemIndicator>
                  </span>
                  <span className={styles.name}>
                    <span className={styles.city}>{option.city}</span>
                    <span className={styles.zone}>{option.value.replaceAll("_", " ")}</span>
                  </span>
                  <span className={styles.offset}>{option.offset}</span>
                </Combobox.Item>
              )}
            </Combobox.List>
            <p className={styles.footer}>Current UTC offsets, including daylight saving.</p>
          </Combobox.Popup>
        </Combobox.Positioner>
      </Combobox.Portal>
    </Combobox.Root>
  );
}

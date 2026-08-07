# Usability rating — 14 cases

Score each output on four yes/no points. Write 1 for yes, 0 for no.
A case passes only if all four are 1.

  names_cause         Does it name a specific mechanism (e.g. "compressor
                      short-cycling"), not just "an anomaly" or "high usage"?
  states_evidence     Does it say what in the data supports that — the shape,
                      the timing, the temperature, the magnitude?
  specific_next_step  Could you act on it without asking anyone? Names a trade,
                      a component, an hour to watch, or a thing to log.
  avoids_jargon       Could a non-technical operations manager read it unaided?
                      Undefined engineering terms in the manager-facing text
                      count as a failure; the technician symptom line is exempt.

You are scoring how it READS, not whether it is CORRECT. A confidently wrong
explanation that names a cause, cites evidence and gives a clear next step
scores 4. Do not look up the answer, and do not confer with the other rater.

---


## ANO-2000

**Explanation.** Refrigeration load jumped to roughly three times normal in the early morning and stayed there for three hours before dropping back, at a time when no staff activity or warm weather could explain it. A cooling system running flat out for hours in cool overnight conditions means it is struggling to hold temperature rather than responding to demand. This is the signature of a compressor working continuously against a fault, and it risks product temperature excursions if left.

**Recommended action.** dispatch — Send a refrigeration technician to Zone A today to inspect the lead compressor and its controls, starting with suction and discharge pressures and run-time logs for the 04:00-07:00 window.

**Symptom for the technician.** Compressor running continuously without cycling off, high discharge / low suction pressure, elevated superheat, and suction line or head temperatures above normal with the zone failing to pull down to setpoint.


## ANO-2001

**Explanation.** Power draw on this refrigeration zone climbed steadily over four hours and never settled back down, even as the outdoor temperature fell in the evening. That combination — rising effort while conditions get easier — points to the cooling system losing its ability to hold temperature and running harder and harder to compensate. This is the signature of a gradual mechanical problem such as a loss of refrigerant charge, not a busy afternoon or a metering glitch.

**Recommended action.** dispatch — Send a refrigeration technician to Zone B tonight to leak-check the circuit and verify charge and suction pressure before product temperature is compromised.

**Symptom for the technician.** Progressive rise in run time with low refrigerant charge: check suction pressure and superheat, look for low subcooling, iced or starved evaporator coil, oil traces at joints and service valves, and confirm compressor is not short-cycling while box temperature drifts above setpoint.


## ANO-2002

**Explanation.** The unit jumped to nearly three times its normal night-time draw, dropped back, then did exactly the same thing two hours later on a cool evening when heating and cooling demand should have been low and steady. Load that size is well within what the unit can physically pull, so this is real electricity being used, not a meter error, and the repeating on-off pattern points to the air handling side of the unit straining and cycling rather than running normally. Because it has already happened twice in one night, it is worth putting eyes on the unit before it fails outright.

**Recommended action.** dispatch — Send an HVAC mechanic to inspect HVAC Unit 2's supply fan assembly and motor first, then check filters and damper position; ask them to attend during the evening if possible since the events fall around 22:00 and midnight.

**Symptom for the technician.** Repeated short-cycling on HVAC Unit 2 with abnormally high fan motor amp draw — check supply fan motor amps against nameplate, bearing noise and belt condition, blade balance and any obstruction, plus static pressure across the filter bank and damper actuator position for restricted airflow driving the motor over-current.


## ANO-2003

**Explanation.** The unit jumped to nearly four times its normal overnight draw and then held there flat for four straight hours, with no return toward normal. Outdoor conditions were mild and unchanging, so there is no weather or business reason for the extra load, and it began in the early morning with no shift change. A sustained step change like this points to an HVAC component running hard continuously — most likely a fan or drive fault forcing the unit to run without achieving its setpoint.

**Recommended action.** dispatch — Send an HVAC technician to inspect HVAC Unit 1 this morning, starting with the supply fan motor, belt and drive controls, and confirm whether the unit has been running continuously since 04:00.

**Symptom for the technician.** Supply fan running continuously at full speed without reaching setpoint — check for seized or failing fan motor bearings, slipping or broken belt, motor drawing above nameplate amps, and blocked or stuck-closed dampers forcing high static pressure.


## ANO-2004

**Explanation.** The southern lighting circuit drew several times its normal load for a single hour on a Saturday morning, then dropped straight back to normal without any sign of a metering gap before or after. That pattern is consistent with the lighting controls briefly switching a large number of zones on at once — for example a stuck relay, an override, or a schedule conflict — rather than with normal weekend activity, which does not change lighting demand this sharply. The load is high but still within what the circuit could physically carry, so it should be treated as a possible control fault and watched.

**Recommended action.** monitor — Pull the lighting control schedule and override log for Lighting Grid South around Saturday 10:00, and watch that circuit hourly for the next 24 hours; a second reading near 90 kWh/hr, or any hour above roughly 40 kWh/hr outside scheduled lighting periods, confirms a stuck relay or failed override and warrants an electrician.


## ANO-2005

**Explanation.** Power draw on the chilled zone climbed steadily over three consecutive hours on a cool Sunday evening, when there is no throughput or weather reason for the units to work harder. That progressive escalation is the signature of a cooling system losing efficiency and running longer and longer to hold temperature. It is not a metering error, because the load stayed within what the zone can physically draw and persisted across several hours.

**Recommended action.** dispatch — Send a refrigeration engineer to Refrigeration Zone A tonight to check charge level and look for oil traces or icing at the evaporator and line joints; also pull the zone's temperature log for 20:00-23:00 Sunday.

**Symptom for the technician.** Progressive loss of cooling capacity with extended or continuous compressor run time: check suction pressure and superheat against spec, look for low refrigerant charge, frosted or starved evaporator coil, bubbles in the sight glass, and oily residue at joints, valve stems and brazed connections.


## ANO-2006

**Explanation.** The lighting circuit jumped far above its normal evening draw for a single hour, then settled, but the two hours after that stayed at roughly double the usual level instead of dropping off for the night. That pattern is consistent with the lighting control system misfiring and leaving banks energised outside their schedule, and the very large single-hour reading may also be partly a metering artefact. Because the after-hours load did not return to normal, this is worth watching rather than writing off.

**Recommended action.** monitor — Track Lighting Grid North hourly readings for the next 24 hours, specifically the 20:00 hour and the 22:00-23:00 window; a repeat spike above roughly 90 kWh at 20:00, or overnight consumption staying near 28-30 kWh instead of falling back to about 12 kWh, confirms a lighting control or scheduling fault and should trigger an electrical callout.


## ANO-2007

**Explanation.** The south lighting circuit drew a little over three times its normal night-time load for a single hour before settling back to its usual level. That amount of extra draw is well within what the lighting circuit can physically deliver, so this is real electricity use rather than a bad meter reading, and the most likely cause is a control or timer fault that left banks of lights energised for an hour outside the scheduled pattern. It corrected itself, so there is no urgency, but a repeat at the same hour would point to a faulty schedule or a stuck relay that needs correcting.

**Recommended action.** monitor — Watch Lighting Grid South at the 23:00 hour for the next 24 hours and flag any repeat above roughly 60 kWh/hr; if it recurs, pull the lighting control schedule and relay logs for that hour before raising a work order.


## ANO-2008

**Explanation.** The unit jumped straight to nearly four times its normal draw and stayed there for four hours with no sign of settling back down. Outdoor conditions were mild, so there is no comfort-cooling reason for the unit to be working this hard, and the load did not follow any shift or occupancy change. That step-and-hold pattern points to a mechanical problem in the air-handling side that is forcing the unit to run flat out.

**Recommended action.** dispatch — Send an HVAC technician to HVAC Unit 2 this morning and have them start at the supply fan assembly and motor, checking amp draw against nameplate before the unit runs another full day at this load.

**Symptom for the technician.** Supply fan running with abnormally high motor amp draw and no return to baseline: check for seized or dragging fan bearings, slipping or broken belt, fan running in stall against a blocked or closed damper, and confirm airflow and static pressure across the coil.


## ANO-2009

**Explanation.** The refrigeration compressors jumped to roughly double their normal draw in the evening and stayed there for eight hours without settling back down, even as it cooled off outside. Cooling demand should have eased overnight, so a load that holds high points to the compressors running continuously instead of cycling normally. That is a hardware problem that will keep wasting energy and risk product temperature until someone looks at it.

**Recommended action.** dispatch — Send a refrigeration technician to the compressor bank tonight or first thing tomorrow to check whether the lead compressor is short-cycling or running continuously without reaching cut-out, and verify suction/discharge pressures and head pressure control.

**Symptom for the technician.** Compressor failing to cycle off / running at full load overnight — check suction and discharge pressures, superheat and subcooling, condenser fan operation and head pressure, and whether the unit is reaching its cut-out setpoint or short-cycling.


## ANO-2010

**Explanation.** The flagged hour sits below the consumption seen in the several hours just before it, and the whole evening's load falls away steadily as the outdoor air cools. That is the signature of air conditioning working through a warm night rather than a piece of equipment misbehaving. There is no step up to a new sustained level and no climb that would point to a mechanical problem.

**Recommended action.** dismiss — Log this as expected warm-night cooling load on HVAC Unit 1 for the 17 July overnight period, and note the elevated evening temperatures so the same midnight hour is not re-flagged in next month's review.


## ANO-2011

**Explanation.** The unit's power draw jumped sharply overnight and then stayed high for five straight hours instead of settling back down, even though it was getting cooler outside and the building was unoccupied. That combination points to the unit running hard continuously because it cannot move air properly, rather than responding to any real demand. Left alone, this kind of continuous overrun usually ends in a motor or belt failure and a much larger repair.

**Recommended action.** dispatch — Send an HVAC technician to inspect the supply fan assembly on HVAC Unit 3 first — check motor amp draw, belt condition and whether the fan is running continuously without a call for cooling.

**Symptom for the technician.** Supply fan running continuously with elevated motor amp draw and low airflow across the coil — check for slipping or shredded belt, seized or dragging bearings, motor overheating, and a stuck or failed control call keeping the unit in continuous run; verify static pressure and coil condition to rule out restricted airflow.


## ANO-2012

**Explanation.** The hour before the spike recorded almost no electricity use at all, which is not physically possible for a lighting circuit that was on, and then the missing usage appeared bundled into the next reading. Usage returned to normal immediately afterwards. This is the meter failing to report for one hour and catching up on the next read, not a real change in how much power the lights drew.

**Recommended action.** dismiss — Log this as a known meter dropout on Lighting Grid South for Friday 13 March 07:00-08:00 so it is excluded from next month's review, and ask metering to check the logger's communications reliability on that circuit.


## ANO-2013

**Explanation.** The reading jumped to six times the normal overnight level for a single hour and then returned exactly to where it had been, with no build-up before and no elevated draw afterwards. A heating and cooling unit running at that level in the middle of a cold night would leave a trace in the surrounding hours, and this one shows none. The pattern is characteristic of a bad reading from the meter rather than any real change in what the equipment was doing.

**Recommended action.** dismiss — Log the 02:00 Tuesday 16 Dec HVAC Unit 1 reading as an isolated meter data spike so it is excluded from next month's exception review, and flag the meter for a routine data-quality check if a second one-hour outlier appears.

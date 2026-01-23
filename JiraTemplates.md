Jira Templates

# OKR Template
```
<h2>📋 Key Result Details</h2>
<p><strong>Owner:</strong> [Manager Name]</p>
<p><strong>Target Quarter:</strong> Q1 / Q2 / Q3 / Q4 2026</p>
<p><strong>Linked Engineering Objective:</strong> [Reference to parent Eng Org Objective]</p>

<h2>🎯 Key Result Statement</h2>
<p><i>[Insert measurable Key Result statement here - e.g., "Reduce P1 production incidents by 40% from baseline of 20/quarter to 12/quarter"]</i></p>

<h2>🧮 Calculation</h2>
<p><i>Calculation used to calculate success of this Key Result.  Calculation should be expressed as a formula.</i></p>

<h2>📊 Scoring Criteria (0.0 - 1.0 Scale)</h2>
<p>Define what each score increment represents for this specific KR:</p>
<ul>
  <li><strong>1.0</strong> = [Full achievement - e.g., 12 or fewer P1 incidents]</li>
  <li><strong>0.7</strong> = [Significant progress - e.g., 14 P1 incidents]</li>
  <li><strong>0.5</strong> = [Moderate progress - e.g., 16 P1 incidents]</li>
  <li><strong>0.3</strong> = [Some progress - e.g., 18 P1 incidents]</li>
  <li><strong>0.0</strong> = [No progress - 20 or more P1 incidents]</li>
</ul>

<h2>📈 Monthly Progress Tracking</h2>
<table>
  <thead>
    <tr>
      <th>Month</th>
      <th>Score (0.0-1.0)</th>
      <th>Status</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>January 2026</td>
      <td><i>[Enter score]</i></td>
      <td>🔴 / 🟡 / 🟢</td>
      <td><i>[Enter notes]</i></td>
    </tr>
    <tr>
      <td>February 2026</td>
      <td><i>[Enter score]</i></td>
      <td>🔴 / 🟡 / 🟢</td>
      <td><i>[Enter notes]</i></td>
    </tr>
    <tr>
      <td>March 2026</td>
      <td><i>[Enter score]</i></td>
      <td>🔴 / 🟡 / 🟢</td>
      <td><i>[Enter notes]</i></td>
    </tr>
  </tbody>
</table>

<p><strong>Color Key:</strong></p>
<ul>
  <li>🟢 <strong>Green (0.7-1.0):</strong> On track / Achieved</li>
  <li>🟡 <strong>Amber (0.4-0.6):</strong> At risk / Moderate progress</li>
  <li>🔴 <strong>Red (0.0-0.3):</strong> Off track / Minimal progress</li>
</ul>

<h2>📝 Q1 End-of-Quarter Summary</h2>
<p><strong>Final Score:</strong> <i>[Average of monthly scores]</i></p>
<p><strong>Achievement Level:</strong> <i>[0.6-0.7 is the target for stretch goals]</i></p>
<p><strong>Key Learnings:</strong></p>
<ul>
  <li><i>[What worked well]</i></li>
  <li><i>[What didn't work]</i></li>
  <li><i>[Adjustments for next quarter]</i></li>
</ul>

<h2>🔗 Related Work</h2>
<p><strong>Supporting Tasks/Stories:</strong> <i>[Link to child tasks in Jira]</i></p>
<p><strong>Dependencies:</strong> <i>[List any blocking items or dependencies]</i></p>

<hr>
<p><em>Note: Scoring 0.6-0.7 indicates ambitious yet achievable goals. Consistently scoring 1.0 may mean goals aren't stretching the team enough. Scores below 0.3 may indicate goals are unrealistic or significant blockers exist.</em></p>
```

# IRIS Template
```
<h2>Goals for this Epic</h2>
<table border="1" style="border-collapse: collapse; width: 100%; text-align: left;">
  <thead>
    <tr>
      <th>Quarter/Fix Version</th>
      <th>Goal(s)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th></th>
      <th>   
		<li></li>
      </th>
    </tr>
  </tbody>
</table>

<h2>Impacted Teams</h2>
<p>
  Work Required: &#x2705; No Impact: &#x274C; Blank: Disposition Unresolved
</p>

<table border="1" style="border-collapse: collapse; width: 100%; text-align: left;">
  <thead>
    <tr>
      <th>Area</th>
      <th>Dev. Manager</th>
      <th>Work</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Compute Service</td>
      <td>Alex Daehnrich</td>
      <td></td>
    </tr>
    <tr>
      <td>Launcher</td>
      <td>Alex Daehnrich</td>
      <td></td>
    </tr>
    <tr>
      <td>Workload Orchestrator</td>
      <td>Alex Daehnrich</td>
      <td></td>
    </tr>
    <tr>
      <td>CAS Service</td>
      <td>Ashutosh Khidrapurkar</td>
      <td></td>
    </tr>
    <tr>
      <td>Viya 4 Host</td>
      <td>Babu Shanker</td>
      <td></td>
    </tr>
    <tr>
      <td>APro and APro Advanced</td>
      <td>Bob Huemmer</td>
      <td></td>
    </tr>
    <tr>
      <td>CS Composites and DevOps</td>
      <td>Bob Huemmer</td>
      <td></td>
    </tr>
    <tr>
      <td>Connect</td>
      <td>George Jeffrey</td>
      <td></td>
    </tr>
    <tr>
      <td>Viya 4 Monitoring</td>
      <td>George Jeffrey</td>
      <td></td>
    </tr>
    <tr>
      <td>CAS</td>
      <td>Rich Wellum</td>
      <td></td>
    </tr>
    <tr>
      <td>Compute Server and Core</td>
      <td>Rich Wellum</td>
      <td></td>
    </tr>
    <tr>
      <td>Procs and Langs</td>
      <td>Titus Lee</td>
      <td></td>
    </tr>
  </tbody>
</table>

<h2>Acceptance Criteria</h2>
Follow one of the <a href="https://rndconfluence.sas.com/display/COMPSVCDIV/Agile+Definitions+and+Jira+Projects#AgileDefinitionsandJiraProjects-AcceptanceCriteria">Compute Division Acceptance Criteria</a> methods (<a href="https://rndconfluence.sas.com/display/COMPSVCDIV/Agile+Definitions+and+Jira+Projects#AgileDefinitionsandJiraProjects-AcceptanceCriteria(VerificationList)">Verfication List</a> or <a href="https://rndconfluence.sas.com/display/COMPSVCDIV/Agile+Definitions+and+Jira+Projects#AgileDefinitionsandJiraProjects-AcceptanceCriteria(Gherkin)">Gherkin</a>).
<h2>Definition of Ready</h2>
<i>Consider following <a href="https://rndconfluence.sas.com/display/COMPSVCDIV/Agile+Definitions+and+Jira+Projects#AgileDefinitionsandJiraProjects-DefinitionofReady">Definition of Ready template for the Compute Division</a>.</i>
<ul>
  <li><i>Dependencies Identified and Resolved</i></li>
  <li><i>Non-functional Requirements are Identified</i></li>
  <li><i>Technical Feasibility Confirmed</i></li>
  <li><i>Acceptance Criteria Reviewed by Dev Managers</i></li>
  <li><i>Priority Confirmed</i></li>
</ul>

<h2>Definition of Done</h2>
<i>Consider following <a href="https://rndconfluence.sas.com/display/COMPSVCDIV/Agile+Definitions+and+Jira+Projects#AgileDefinitionsandJiraProjects-DefinitionofDone">Definition of Done template for the Compute Division</a>.</i>
<ul>
  <li><i>The code is complete</i></li>
  <li><i>Unit Tests are written and pass</i></li>
  <li><i>Integration testing passes</i></li>
  <li><i>Regression suite passes</i></li>
  <li><i>Performance testing passes</i></li>
  <li><i>Integration testing passes</i></li>
  <li><i>Code merged to main branch</i></li>
</ul>

<h2>Assumptions</h2>
<i>What assumptions and clarifications need to be made to properly deliver on this requirement?</i>
<ul>
  <li></li>
</ul>
```
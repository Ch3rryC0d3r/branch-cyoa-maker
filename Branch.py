<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Branch Documentation</title>
<style>
  :root {
    --bg: #fdfdfd;
    --text: #222;
    --accent: #2575fc;
    --accent-dark: #6a11cb;
    --code-bg: #1e1e1e;
    --code-text: #f8f8f2;
    --sidebar-bg: #fafafa;
  }
  [data-theme="dark"] {
    --bg: #121212;
    --text: #eaeaea;
    --accent: #90caf9;
    --accent-dark: #6a11cb;
    --code-bg: #2d2d2d;
    --code-text: #f8f8f2;
    --sidebar-bg: #1a1a1a;
  }
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    display: flex;
  }
  header {
    background: linear-gradient(135deg, var(--accent-dark) 0%, var(--accent) 100%);
    color: white;
    padding: 2rem;
    text-align: center;
  }
  header h1 { margin: 0; font-size: 2.2rem; }
  #sidebar {
    width: 280px;
    background: var(--sidebar-bg);
    border-right: 1px solid #4443;
    padding: 1rem;
    height: 100vh;
    position: sticky;
    top: 0;
    overflow-y: auto;
    flex-shrink: 0;
  }
  #sidebar h2 { font-size: 1rem; color: var(--accent); margin-top: 0.5rem; }
  #sidebar ul { list-style: none; padding: 0; margin: 0.5rem 0; }
  #sidebar li { margin: 0.25rem 0; }
  #sidebar a {
    text-decoration: none;
    color: var(--text);
    font-size: 0.9rem;
    transition: color 0.2s;
  }
  #sidebar a.active { font-weight: bold; color: var(--accent); }
  #searchBar {
    width: 100%; padding: 0.5rem; margin-bottom: 1rem;
    border: 1px solid #ccc; border-radius: 6px;
    background: var(--bg); color: var(--text);
  }
  main {
    flex: 1;
    max-width: 1000px;
    margin: 2rem auto;
    padding: 1rem 2rem;
    background: var(--bg);
    border-radius: 10px;
  }
  .breadcrumb { font-size: 0.9rem; margin-bottom: 1rem; color: #888; }
  .breadcrumb span { color: var(--accent); }
  h2 {
    border-bottom: 3px solid var(--accent);
    padding-bottom: 0.4rem;
    margin-top: 2rem;
  }
  h3 { margin-top: 1.5rem; cursor: pointer; }
  .collapsible { margin-left: 1rem; display: none; }
  footer {
    text-align: center;
    margin: 2rem 0;
    color: #777;
    font-size: 0.9rem;
  }
  code, pre {
    background: var(--code-bg);
    color: var(--code-text);
    border-radius: 6px;
    font-family: Consolas, monospace;
  }
  pre {
    padding: 1rem;
    overflow-x: auto;
    position: relative;
    margin: 1rem 0;
  }
  .copy-btn {
    position: absolute;
    top: 8px; right: 8px;
    background: var(--accent);
    color: white;
    border: none;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
  }
  .example {
    background: #f0f8ff11;
    border-left: 5px solid var(--accent);
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 6px;
  }
  #themeToggle {
    position: absolute; top: 1rem; right: 1rem;
    background: white; border: none;
    border-radius: 50%; width: 36px; height: 36px;
    cursor: pointer; font-size: 1.2rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  }
</style>
</head>
<body data-theme="light">

<!-- Sidebar -->
<aside id="sidebar">
  <input type="text" id="searchBar" placeholder="Search...">
  <nav>
    <ul id="toc"></ul>
  </nav>
</aside>

<!-- Main -->
<div style="flex:1">
<header>
  <button id="themeToggle">🌙</button>
  <h1>🌿 Branch Leaf Documentation</h1>
  <p>Documentation for leaves with Branch.</p>
</header>
<main>

<h2>What is a Leaf?</h2>
<p>A <strong>Leaf</strong> is a single option line inside a Node. It's what players can pick. Each Leaf can:</p>
<ul>
  <li>Show <strong>Text</strong> for the choice.</li>
  <li>Point to another Node (<strong>Next</strong>).</li>
  <li>Check <strong>Conditions</strong> for display.</li>
  <li>Execute <strong>Actions</strong> when chosen.</li>
</ul>

<h2>Leaf Structure</h2>
<p>Leaves are written as:</p>
<pre><code>Text | Next | Condition | Actions</code></pre>

<ul>
  <li><strong>Text</strong> → What the player sees (supports <code>{var}</code> substitution).</li>
  <li><strong>Next</strong> → The Node ID to go to (can be a single ID, random from a list like <code>1/2/3</code>, or a variable).</li>
  <li><strong>Condition</strong> → Optional checks that must be true for the Leaf to be visible.</li>
  <li><strong>Actions</strong> → Things that happen when the player chooses this Leaf.</li>
</ul>

<div class="example">
  <p><strong>Simple Example:</strong></p>
  <pre><code>Take the sword | 5 | has_item:Key | add_item:Sword</code></pre>
</div>

<h2>Comments</h2>
<p>You can add comments to your Leaf options to leave notes for yourself or to temporarily disable a line. The game engine will ignore any line that starts with a hash symbol (<code>#</code>).</p>
<div class="example">
  <p><strong>Example with comments:</strong></p>
  <pre><code># This is a choice to go left.
Go left | 2 | | 
Go right | 3 | | 
# TODO: Add a condition for this secret path later
# A secret path | 4 | has_item:key | </code></pre>
</div>

<h2>Conditions</h2>
<p>Conditions control whether a Leaf is visible to the player. You can chain multiple conditions together using <code>&</code> or <code>;</code>. All conditions must be true for the Leaf to appear.</p>
<ul>
  <li><code>has_item:Sword</code> → Checks if the player has the "Sword" item.</li>
  <li><code>not_has_item:Key</code> → Checks if the player does <strong>not</strong> have the "Key" item.</li>
  <li><code>HP &lt;= 0</code> → Allows for complex mathematical and boolean checks using variables.</li>
  <li><code>var:CLICKS==1</code> → An explicit way to check a variable's value (the <code>var:</code> prefix is optional).</li>
</ul>

<div class="example">
  <p><strong>Chance-Based Visibility Example:</strong></p>
  <pre><code>Search the forest | 8 | chance(40) |  
Search the cave | 9 | chance(90) |</code></pre>
  <p>In this node, "Search the forest" has a 40% chance to be visible, and "Search the cave" has a 90% chance to be visible. It's possible for both, one, or neither to appear.
  This is different from the <code>weighted()</code> <em>action</em>, which picks one outcome from a pool.
  You can mix this with other conditions, for example: <code>has_item:torch & chance(50)</code>. The leaf will only be visible if the player has a torch AND the 50% chance roll succeeds.
  </p>
</div>

<div class="example">
  <p><strong>Checking a Header Character (hlet):</strong></p>
  <pre><code>This choice is only visible if the second letter of this node's header is 'x' | 10 | hlet:2=x | </code></pre>
  <p>The <code>hlet</code> condition (short for "header letter") checks a specific character in the current node's header string. It's case-sensitive. The index is 1-based, not 0-based.</p>
</div>

<div class="example">
  <p><strong>Timed Choice Example (lifetime):</strong></p>
  <pre><code>Quick, grab the idol! | 12 | lifetime(10) | add_item:Idol</code></pre>
  <p>The <code>lifetime(SECONDS)</code> condition makes a choice available for only a limited time. When the node loads, a 10-second timer starts for this choice. If the player doesn't pick it within that time, the choice will disappear. This can be combined with other conditions, like <code>has_item:torch & lifetime(5)</code>.</p>
</div>

<p>You can also use <code>!</code> before any condition to negate its result. This is a powerful shortcut for writing "not" conditions.</p>
<div class="example">
  <p><strong>Example:</strong></p>
  <pre><code>Don't talk to the dragon | 2 | !has_item:Sword | </code></pre>
  <p>This choice is only visible if the player does <strong>not</strong> have the Sword. It works the same as <code>not_has_item:Sword</code>.</p>
  <p>You can also use it with other conditions:</p>
  <pre><code>The safe is locked... | 5 | !hlet:4=K & !has_item:Key |</code></pre>
  <p>This choice will appear if the fourth character of the header is not 'K' AND the player does not have a "Key" in their inventory.</p>
</div>

<h2>Actions</h2>
<p>Actions are commands that execute when a Leaf is chosen. You can chain multiple actions together using <code>&</code> or <code>;</code>.</p>

<h3>Variables</h3>
<ul>
  <li><code>gold = 100</code> → Assigns a value to a variable.</li>
  <li><code>gold += 5</code> → Modifies a variable's value (also supports <code>-=</code>, <code>*=</code>, <code>/=</code>).</li>
</ul>

<h3>Inventory</h3>
<ul>
  <li><code>add_item:Sword</code> → Adds an item to the player's inventory.</li>
  <li><code>remove_item:Key</code> → Removes an item from the player's inventory.</li>
  <li><code>clearinv</code> → Wipes the entire inventory.</li>
  <li><code>rename_item:OLD,NEW</code> → Changes the name of an item in the player's inventory from <code>OLD</code> to <code>NEW</code>.</li>
</ul>

<div class="example">
  <p><strong>Renaming an Item Example:</strong></p>
  <pre><code>You polish the sword until it shines. | 5 | | rename_item:Rusty Sword,Polished Sword</code></pre>
  <p>If the player's inventory contains "Rusty Sword" when this option is chosen, its name will be changed to "Polished Sword".</p>
</div>

<h3>Utility Actions</h3>
<ul>
  <li><code>clamp(HP:0,100)</code> → Ensures the 'HP' variable stays between 0 and 100. If HP was 110, it becomes 100. If it was -5, it becomes 0. The min/max values can be numbers or other variables.</li>
  <li><code>consume(Key:goto:12)</code> → A shortcut action. It first checks if the player has "Key". If so, it removes "Key" from the inventory and then executes the action (<code>goto:12</code>). If the player doesn't have the item, nothing happens.</li>
  <li><code>rlet:INDEX:CHAR</code> → A specific action that replaces a character in the current node's header. See below for details.</li>
</ul>

<div class="example">
  <p><strong>Replacing a Header Character (rlet):</strong></p>
  <pre><code>Swap the second letter to 's' | 5 | | rlet:2:s</code></pre>
  <p>The <code>rlet</code> action (short for "replace letter") changes a specific character in the current node's header string. The index is 1-based, not 0-based.</p>
</div>

<h3>Flow Control</h3>
<ul>
  <li><code>once:gold+=1</code> → Runs this action only once ever.</li>
  <li><code>once:&gt;gold+=1</code> → Runs only the first action once.</li>
  <li><code>once:&gt;&gt;gold+=1;log:done</code> → Runs all actions, but only once total.</li>
  <li><code>once:&lt;gold+=1&gt;log:done</code> → Conditional gold increase (if condition true), but log always, only the first time.</li>
</ul>

<h3>Randomization</h3>
<ul>
  <li><code>randr(damage:5,20)</code> → Sets the 'damage' variable to a random number between 5 and 20.</li>
  <li><code>rands(weather:Sunny,Cloudy)</code> → Sets the 'weather' variable to either "Sunny" or "Cloudy".</li>
  <li><code>weighted(weather:Sunny=70,Rain=30)</code> → Sets 'weather' based on weights. "Sunny" has a 70% chance, "Rain" has a 30% chance.</li>
  <li><code>chance(30)&gt;gold+=10</code> → A 30% chance to execute the success action (<code>gold+=10</code>).</li>
  <li><code>chance(30)&gt;gold+=10&gt;gold-=5</code> → A 30% chance for success (<code>gold+=10</code>), otherwise the fail action (<code>gold-=5</code>) is executed.</li>
</ul>

<h3>Loops</h3>
<ul>
  <li><code>repeat:3&gt;gold+=1</code> → Repeats the <em>first</em> action (<code>gold+=1</code>) 3 times.</li>
  <li><code>repeat:3&gt;&gt;gold+=1;log:done</code> → Repeats <em>all</em> actions 3 times.</li>
  <li><code>repeat:3:&lt;gold+=1&gt;log:done</code> → Adds gold if the condition is true, but always logs.</li>
</ul>

<h3>Instant Actions (@)</h3>
<p>Instant actions are special actions that run automatically when a player enters a node, <em>before</em> they get to make a choice. They are defined on their own line, starting with <code>@</code>.</p>
<pre><code>@HP-=5
@if(is_cursed)&gt;add_item:Curse</code></pre>

<h3>Timed Instant Actions (@timer)</h3>
<p>A special type of instant action that executes after a delay. Supports the same separators as <code>if</code> and <code>repeat</code>.</p>
<pre><code>@timer(SECONDS):&gt;ACTION
@timer(SECONDS):&gt;&gt;ACTION1;ACTION2
@timer(SECONDS):&lt;CACTS&gt;UACTS</code></pre>
<ul>
  <li><strong>&gt;</strong> → Only runs the first action after the timer expires.</li>
  <li><strong>&gt;&gt;</strong> → Runs all actions after the timer expires.</li>
  <li><strong>&lt;...&gt;</strong> → Conditional actions inside the block, unconditional actions outside it.</li>
</ul>
<div class="example">
  <p><strong>Example:</strong></p>
  <pre><code>@timer(5):&gt;&gt;goto:10;HP-=5</code></pre>
  <p>After 5 seconds, the player is sent to Node 10 and loses 5 HP.</p>
</div>

<h2>Conditional Actions (if)</h2>
<p>The <code>if</code> statement is a powerful action that lets you run other actions only if a certain condition is met. It has a few different forms.</p>

<h3>1. Single Conditional Action (&gt;)</h3>
<p>This is the simplest form. If the condition is true, it executes only the <strong>first</strong> action that follows the <code>&gt;</code>.</p>
<div class="example">
  <pre><code>if(has_item:Sword)&gt;damage+=10;cost=50</code></pre>
  <p>In this case, if the player has a sword, <code>damage</code> will increase by 10. The <code>cost=50</code> action is <strong>not</strong> part of the if-statement and will always run.</p>
</div>

<h3>2. Multi-Action Block (&gt;&gt;)</h3>
<p>By using <code>&gt;&gt;</code>, you can tell the if-statement to treat <strong>all</strong> subsequent actions on the line as a single conditional block.</p>
<div class="example">
  <pre><code>if(gold&gt;=price)&gt;&gt;potions+=1;gold-=price</code></pre>
  <p>Here, if <code>gold</code> is greater than or equal to <code>price</code>, <strong>both</strong> actions (<code>potions+=1</code> and <code>gold-=price</code>) will be executed.</p>
</div>

<h3>3. Advanced Conditional/Unconditional Block (&lt;...&gt;)</h3>
<p>This is the most flexible syntax. It allows you to define a block of actions that run if the condition is true, followed by actions that run regardless.</p>
<pre><code>if(condition):&lt;conditional_actions&gt;unconditional_actions</code></pre>
<div class="example">
  <pre><code>if(gold&gt;=price):&lt;potions+=1;gold-=price&gt;price*=2</code></pre>
  <p>Let's break it down:</p>
  <ul>
    <li><strong>Condition:</strong> <code>gold&gt;=price</code></li>
    <li><strong>Conditional Actions:</strong> <code>potions+=1;gold-=price</code> (inside the <code>&lt;...&gt;</code>) will only run if the condition is true.</li>
    <li><strong>Unconditional Action:</strong> <code>price*=2</code> (after the <code>&lt;...&gt;</code>) will <strong>always</strong> run, no matter what the condition was.</li>
  </ul>
</div> 
</main>
<footer>
  <p>Last updated for Branch v0.5.14</p>
  <p>Documentation Version: 1.1</p>
</footer>
</div>

<script>
  // Theme toggle
  const toggle = document.getElementById('themeToggle');
  toggle.addEventListener('click', () => {
    const body = document.body;
    const theme = body.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    body.setAttribute('data-theme', theme);
    toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  });

  // TOC build
  const toc = document.getElementById('toc');
  document.querySelectorAll('h2, h3').forEach(el => {
    if(!el.id) el.id = el.textContent.toLowerCase().replace(/\s+/g,'-');
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.textContent = el.textContent;
    a.href = '#' + el.id;
    li.appendChild(a);
    if(el.tagName === 'H3') li.style.marginLeft = '1rem';
    toc.appendChild(li);
  });

  // Scroll spy
  const sections = document.querySelectorAll('h2, h3');
  window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(sec => {
      const top = sec.offsetTop - 100;
      if (pageYOffset >= top) current = sec.id;
    });
    document.querySelectorAll('#toc a').forEach(a => {
      a.classList.remove('active');
      if (a.getAttribute('href') === '#' + current) a.classList.add('active');
    });
  });

  // Search filter
  const searchBar = document.getElementById('searchBar');
  searchBar.addEventListener('input', () => {
    const term = searchBar.value.toLowerCase();
    sections.forEach(sec => {
      if(sec.textContent.toLowerCase().includes(term)) sec.style.display = '';
      else sec.style.display = 'none';
    });
  });

  // Copy buttons
  document.querySelectorAll('pre').forEach(pre => {
    const btn = document.createElement('button');
    btn.textContent = 'Copy';
    btn.className = 'copy-btn';
    pre.appendChild(btn);
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(pre.innerText);
      btn.textContent = 'Copied!';
      setTimeout(()=>btn.textContent='Copy', 1200);
    });
  });

  // Collapsible h3 sections
  document.querySelectorAll('h3').forEach(h3 => {
    let next = h3.nextElementSibling;
    const div = document.createElement('div');
    div.classList.add('collapsible');
    while(next && !['H2','H3'].includes(next.tagName)) {
      const sibling = next;
      next = next.nextElementSibling;
      div.appendChild(sibling);
    }
    h3.parentNode.insertBefore(div, next);
    h3.addEventListener('click', () => {
      div.style.display = div.style.display === 'block' ? 'none' : 'block';
    });
  });
</script>
</body>
</html>

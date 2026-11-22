const {chromium}=require('/Users/g1/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1100,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('file:///private/tmp/knee-preview.html');
    const frame=page.frameLocator('iframe');
    const angle=frame.locator('[data-live="angle"]');
    await angle.waitFor();
    await frame.getByRole('button',{name:'Run simulation'}).click();
    await page.waitForTimeout(1700);
    assert.notEqual(await angle.textContent(),'10.0°');
    await frame.getByRole('button',{name:'Pause',exact:true}).click();
    const paused=await angle.textContent();await page.waitForTimeout(250);assert.equal(await angle.textContent(),paused);
    await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(200);assert.equal(await angle.textContent(),paused,'theme preserves simulation');
    await page.emulateMedia({colorScheme:'light'});
    await frame.locator('[data-param="mode"]').selectOption('manual');
    await frame.locator('[data-param="manualExt"]').fill('120');
    await frame.getByRole('button',{name:'Run simulation'}).click();
    await page.waitForTimeout(1700);
    const pressure=await frame.locator('[data-live="pe"]').textContent();
    assert.ok(parseFloat(pressure)>110,'manual channel pressurizes');
    await frame.locator('[data-param="assist"]').uncheck();
    await page.waitForTimeout(1300);
    assert.ok(parseFloat(await frame.locator('[data-live="pe"]').textContent())<10,'disable vents pressure');
    await frame.getByRole('button',{name:'Pause',exact:true}).click();
    await frame.locator('[data-param="mode"]').selectOption('hold');
    await frame.locator('[data-param="target"]').fill('90');
    assert.equal(await frame.locator('[data-value="target"]').textContent(),'90°');
    await frame.locator('[data-series="target"]').click();
    assert.equal(await frame.locator('[data-series="target"]').getAttribute('aria-pressed'),'false');
    await frame.locator('[data-series="target"]').click();
    await frame.locator('[data-param="mode"]').selectOption('cycle');
    await frame.locator('[data-param="assist"]').check();
    await frame.getByRole('button',{name:'Run simulation'}).click();
    await page.waitForTimeout(2000);
    await frame.getByRole('button',{name:'Pause',exact:true}).click();
    const targetFrame=page.frames().find(f=>f!==page.mainFrame());
    const sizeFrame=async()=>{
      const height=await targetFrame.evaluate(()=>document.documentElement.scrollHeight);
      await page.locator('iframe').evaluate((e,h)=>{e.style.height=h+'px';},height);
    };
    await sizeFrame();
    await page.screenshot({path:'/private/tmp/knee-desktop.png',fullPage:true});
    const layout=await targetFrame.evaluate(()=>{
      const r=document.getElementById('knee-assistance-lab');
      return {width:r.clientWidth,scroll:r.scrollWidth,svgCount:r.querySelectorAll('svg').length,d3:typeof d3};
    });
    assert.ok(layout.scroll<=layout.width+1,'desktop fits');
    await page.setViewportSize({width:360,height:1200});await page.waitForTimeout(250);
    await frame.getByText('Adjust model assumptions',{exact:true}).click();await page.waitForTimeout(150);
    await sizeFrame();
    const mobile=await targetFrame.evaluate(()=>{
      const r=document.getElementById('knee-assistance-lab');
      const bad=[...r.querySelectorAll('input,select,button,output,summary')].filter(e=>{
        const b=e.getBoundingClientRect();return b.width>0&&(b.left<0||b.right>innerWidth+1);
      }).map(e=>e.outerHTML.slice(0,100));
      return {width:r.clientWidth,scroll:r.scrollWidth,bad};
    });
    await page.setViewportSize({width:360,height:2300});await page.waitForTimeout(150);
    await sizeFrame();await page.screenshot({path:'/private/tmp/knee-mobile.png',fullPage:true});
    await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(150);
    await page.screenshot({path:'/private/tmp/knee-dark.png',fullPage:true});
    await page.emulateMedia({colorScheme:'light'});
    assert.ok(mobile.scroll<=mobile.width+1,'mobile fits');assert.deepEqual(mobile.bad,[]);
    for(const width of [320,736,1024]) {
      await page.setViewportSize({width,height:1200});await page.waitForTimeout(100);
      const issues=await targetFrame.evaluate(()=>{
        const root=document.getElementById('knee-assistance-lab'),bound=root.getBoundingClientRect();
        return [...root.querySelectorAll('input,select,button,output,summary')].filter(e=>{
          const r=e.getBoundingClientRect();return r.width>0&&(r.left<bound.left-1||r.right>bound.right+1);
        }).map(e=>e.outerHTML.slice(0,100));
      });
      assert.deepEqual(issues,[],`controls fit at ${width}`);
      for(const svg of await frame.locator('.plot').all()) {
        const overlaps=await svg.evaluate(e=>{
          const b=[...e.querySelectorAll('text')].map(t=>({text:t.textContent,box:t.getBoundingClientRect()}));
          const errors=[];
          b.forEach((a,i)=>b.slice(i+1).forEach(c=>{if(a.box.right>c.box.left+1&&a.box.left<c.box.right-1&&a.box.bottom>c.box.top+1&&a.box.top<c.box.bottom-1)errors.push([a.text,c.text]);}));
          return errors;
        });
        assert.deepEqual(overlaps,[],`chart labels fit at ${width}`);
      }
    }
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,layout,mobile,errors},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

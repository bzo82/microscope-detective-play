import { chromium } from 'playwright';
import fs from 'node:fs';
const browser=await chromium.launch({headless:true});
fs.mkdirSync('qa-screenshots',{recursive:true});
for(const [name,viewport] of [['mobile',{width:390,height:844}],['desktop',{width:1280,height:900}]]){
 const page=await browser.newPage({viewport,deviceScaleFactor:1,locale:'he-IL'});
 const errors=[];page.on('pageerror',err=>errors.push(err.message));
 await page.goto('https://bzo82.github.io/microscope-detective-play/',{waitUntil:'domcontentloaded',timeout:30000});
 await page.locator('#welcomeView').waitFor({state:'visible',timeout:15000});
 await page.screenshot({path:'qa-screenshots/'+name+'-welcome.png',fullPage:true});
 await page.locator('#startBtn').click();
 await page.locator('#answers button').first().waitFor({state:'visible',timeout:25000});
 await page.screenshot({path:'qa-screenshots/'+name+'-question.png',fullPage:true});
 if(errors.length)throw Error(errors.join('; '));
 console.log(name,'screenshots captured; no JavaScript errors');
 await page.close();
}
await browser.close();

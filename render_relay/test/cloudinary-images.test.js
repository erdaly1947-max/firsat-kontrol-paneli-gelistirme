import test from "node:test";
import assert from "node:assert/strict";
import { createRelayServer } from "../server.js";

const PNG = Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,1]);
const PREFIX = "fkp_screenshot_";
const ACTIVE = "fkp-active";

function seededResource(id, daysAgo, filename, tags = [ACTIVE]) {
  return {
    public_id:PREFIX+id, asset_id:"asset-"+id,
    created_at:new Date(Date.now()-daysAgo*86400000).toISOString(),
    bytes:PNG.length, format:"png",
    secure_url:"https://res.cloudinary.com/CCY85JMZ/image/upload/"+PREFIX+id+".png",
    tags:[...tags], context:{custom:{filename_b64:Buffer.from(filename,"utf8").toString("base64url")}},
  };
}

test("Cloudinary screenshot commit replaces oldest image and exposes only three active images", async (t) => {
  const oldEnv={
    CLOUDINARY_CLOUD_NAME:process.env.CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY:process.env.CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET:process.env.CLOUDINARY_API_SECRET,
    REPORT_RELAY_TOKEN:process.env.REPORT_RELAY_TOKEN,
  };
  process.env.CLOUDINARY_CLOUD_NAME="CCY85JMZ";
  process.env.CLOUDINARY_API_KEY="test-api-key";
  process.env.CLOUDINARY_API_SECRET="test-api-secret";
  process.env.REPORT_RELAY_TOKEN="test-token";
  const ids=["11111111-1111-4111-8111-111111111111","22222222-2222-4222-8222-222222222222","33333333-3333-4333-8333-333333333333"];
  let resources=[seededResource(ids[0],3,"oldest.png"),seededResource(ids[1],2,"middle.png"),seededResource(ids[2],1,"newest.png")];
  const originalFetch=globalThis.fetch;
  globalThis.fetch=async(input,init={})=>{
    const url=new URL(String(input));
    const method=String(init.method||"GET").toUpperCase();
    if(url.hostname==="api.cloudinary.com"){
      assert.equal(new Headers(init.headers||{}).get("authorization")?.startsWith("Basic "),true);
      if(url.pathname.endsWith("/image/upload")&&method==="POST"){
        const form=init.body, publicId=form.get("public_id"), file=form.get("file"), custom={};
        for(const item of String(form.get("context")||"").split("|")){
          const pair=item.split("=");
          if(pair.length>=2)custom[pair[0]]=pair.slice(1).join("=");
        }
        const resource={
          public_id:publicId,asset_id:"asset-"+publicId,created_at:new Date().toISOString(),
          bytes:file.size,format:file.type==="image/png"?"png":"jpg",
          secure_url:"https://res.cloudinary.com/CCY85JMZ/image/upload/"+publicId+(file.type==="image/png"?".png":".jpg"),
          tags:String(form.get("tags")||"").split(",").filter(Boolean),context:{custom},
        };
        resources.push(resource);
        return new Response(JSON.stringify(resource),{status:200,headers:{"Content-Type":"application/json"}});
      }
      if(url.pathname.endsWith("/resources/image/upload")&&method==="GET"){
        const prefix=url.searchParams.get("prefix")||"";
        return new Response(JSON.stringify({resources:resources.filter((item)=>item.public_id.startsWith(prefix))}),{status:200,headers:{"Content-Type":"application/json"}});
      }
      if(url.pathname.endsWith("/image/tags")&&method==="POST"){
        const form=new URLSearchParams(String(init.body||"")),tag=form.get("tag"),command=form.get("command"),publicIds=form.getAll("public_ids[]");
        for(const item of resources){
          if(!publicIds.includes(item.public_id))continue;
          const set=new Set(item.tags);
          if(command==="add")set.add(tag);
          if(command==="remove")set.delete(tag);
          item.tags=[...set];
        }
        return new Response(JSON.stringify({public_ids:publicIds}),{status:200,headers:{"Content-Type":"application/json"}});
      }
      if(url.pathname.endsWith("/resources/image/upload")&&method==="DELETE"){
        const publicIds=new URLSearchParams(String(init.body||"")).getAll("public_ids[]"),deleted={};
        for(const id of publicIds){
          const before=resources.length;
          resources=resources.filter((item)=>item.public_id!==id);
          deleted[id]=resources.length<before?"deleted":"not_found";
        }
        return new Response(JSON.stringify({deleted,partial:false}),{status:200,headers:{"Content-Type":"application/json"}});
      }
      return new Response(JSON.stringify({error:{message:"unexpected endpoint"}}),{status:404,headers:{"Content-Type":"application/json"}});
    }
    if(url.hostname==="res.cloudinary.com")return new Response(PNG,{status:200,headers:{"Content-Type":"image/png"}});
    return originalFetch(input,init);
  };
  const server=createRelayServer();
  await new Promise((resolve,reject)=>{server.once("error",reject);server.listen(0,"127.0.0.1",resolve);});
  t.after(async()=>{
    await new Promise((resolve)=>server.close(()=>resolve()));
    globalThis.fetch=originalFetch;
    for(const [key,value] of Object.entries(oldEnv)){if(value===undefined)delete process.env[key];else process.env[key]=value;}
  });
  const base="http://127.0.0.1:"+server.address().port;
  const stageResponse=await originalFetch(base+"/api/images/stage",{
    method:"POST",
    headers:{Authorization:"Bearer test-token","Content-Type":"image/png","X-Image-Name-B64":Buffer.from("new.png").toString("base64url")},
    body:PNG,
  });
  assert.equal(stageResponse.status,200);
  const stage=await stageResponse.json();
  assert.equal(typeof stage.staged_id,"string");
  const commitResponse=await originalFetch(base+"/api/images/commit",{
    method:"POST",headers:{Authorization:"Bearer test-token","Content-Type":"application/json"},
    body:JSON.stringify({staged_ids:[stage.staged_id]}),
  });
  assert.equal(commitResponse.status,200);
  const commit=await commitResponse.json();
  assert.equal(commit.images.length,3);
  assert.ok(commit.images.some((item)=>item.id===stage.staged_id));
  assert.ok(!resources.some((item)=>item.public_id===PREFIX+ids[0]));
  const manifestResponse=await originalFetch(base+"/images/manifest");
  assert.equal(manifestResponse.status,200);
  const manifest=await manifestResponse.json();
  assert.equal(manifest.images.length,3);
  assert.ok(manifest.images.some((item)=>item.filename==="middle.png"));
  assert.ok(manifest.images.some((item)=>item.filename==="newest.png"));
  assert.ok(manifest.images.some((item)=>item.id===stage.staged_id));
  const imageResponse=await originalFetch(base+"/images/"+stage.staged_id);
  assert.equal(imageResponse.status,200);
  assert.equal(imageResponse.headers.get("content-type"),"image/png");
});

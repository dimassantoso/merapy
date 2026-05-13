(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,18566,(e,t,a)=>{t.exports=e.r(76562)},59513,e=>{"use strict";async function t(e,t){let a=await fetch("http://localhost:8080/graphql",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:e,variables:t}),cache:"no-store"});if(!a.ok)throw Error(`GraphQL request failed: ${a.status}`);let r=await a.json();if(r.errors?.length)throw Error(r.errors[0].message);return r.data}let a=`
  query GetAllJob($filter: GetAllJobInputResolver) {
    get_all_job(filter: $filter) {
      meta { page limit total_pages total_records }
      data {
        id task_name arguments retries max_retry
        status error result created_at finished_at
      }
    }
  }
`,r=`
  query GetAllTask {
    get_all_task {
      name module_name total_jobs
      detail { queueing retrying success failure stopped }
    }
  }
`,s=`
  mutation AddJob($param: AddJobInputResolver!) {
    add_job(param: $param)
  }
`,l=`
  mutation RetryJob($job_id: String!) {
    retry_job(job_id: $job_id)
  }
`,n=`
  mutation RetryAllJob($filter: FilterMutateJobInputResolver!) {
    retry_all_job(filter: $filter)
  }
`,i=`
  mutation DeleteJob($job_id: String!) {
    delete_job(job_id: $job_id)
  }
`,o=`
  mutation CleanJob($filter: FilterMutateJobInputResolver!) {
    clean_job(filter: $filter)
  }
`;e.s(["ADD_JOB",0,s,"CLEAN_JOB",0,o,"DELETE_JOB",0,i,"GET_ALL_JOB",0,a,"GET_ALL_TASK",0,r,"RETRY_ALL_JOB",0,n,"RETRY_JOB",0,l,"STATUS_COLORS",0,{QUEUEING:"bg-blue-100 text-blue-800",RETRYING:"bg-yellow-100 text-yellow-800",SUCCESS:"bg-green-100 text-green-800",FAILURE:"bg-red-100 text-red-800",STOPPED:"bg-gray-100 text-gray-700"},"gql",0,t])},54806,e=>{"use strict";var t=e.i(43476),a=e.i(71645),r=e.i(18566),s=e.i(59513);let l=`
  query GetAllJob($filter: GetAllJobInputResolver) {
    get_all_job(filter: $filter) {
      data {
        id task_name arguments retries max_retry interval
        status error result trace_id created_at finished_at
      }
    }
  }
`;function n(){let e=(0,r.useSearchParams)(),n=(0,r.useRouter)(),i=e.get("id")??"",[o,d]=(0,a.useState)(null),[c,u]=(0,a.useState)(!0),[m,x]=(0,a.useState)(null),[b,g]=(0,a.useState)(!1),p=(0,a.useCallback)(async()=>{if(i)try{let e=(await (0,s.gql)(l,{filter:{job_id:i,limit:1}})).get_all_job.data[0]??null;d(e),x(null)}catch(e){x(e instanceof Error?e.message:"Failed to load job")}finally{u(!1)}},[i]);async function h(){if(o){g(!0);try{await (0,s.gql)(s.RETRY_JOB,{job_id:o.id}),await p()}finally{g(!1)}}}async function f(){if(o&&confirm("Delete this job?")){g(!0);try{await (0,s.gql)(s.DELETE_JOB,{job_id:o.id}),n.push(`/task?task_name=${encodeURIComponent(o.task_name)}`)}finally{g(!1)}}}if((0,a.useEffect)(()=>{p();let e=setInterval(p,5e3);return()=>clearInterval(e)},[p]),c)return(0,t.jsx)("div",{className:"p-12 text-center text-gray-400",children:"Loading…"});if(m)return(0,t.jsx)("div",{className:"p-12 text-center text-red-500",children:m});if(!o)return(0,t.jsx)("div",{className:"p-12 text-center text-gray-400",children:"Job not found"});let y=[["ID",(0,t.jsx)("span",{className:"font-mono text-sm",children:o.id})],["Task Name",(0,t.jsx)("button",{onClick:()=>n.push(`/task?task_name=${encodeURIComponent(o.task_name)}`),className:"text-indigo-600 hover:underline font-mono",children:o.task_name})],["Status",(0,t.jsx)("span",{className:`px-2 py-0.5 rounded text-xs font-medium ${s.STATUS_COLORS[o.status]??"bg-gray-100 text-gray-600"}`,children:o.status})],["Retries",`${o.retries} / ${o.max_retry}`],["Interval",o.interval||"—"],["Created At",o.created_at?new Date(o.created_at).toLocaleString():"—"],["Finished At",o.finished_at?new Date(o.finished_at).toLocaleString():"—"],["Trace ID",o.trace_id||"—"],["Arguments",(0,t.jsx)("pre",{className:"bg-gray-50 rounded p-2 text-xs font-mono overflow-auto max-h-40 whitespace-pre-wrap",children:(()=>{try{return JSON.stringify(JSON.parse(o.arguments),null,2)}catch{return o.arguments}})()})],["Result",o.result?(0,t.jsx)("pre",{className:"bg-gray-50 rounded p-2 text-xs font-mono overflow-auto max-h-40 whitespace-pre-wrap",children:(()=>{try{return JSON.stringify(JSON.parse(o.result),null,2)}catch{return o.result}})()}):"—"],["Last Error",o.error?(0,t.jsx)("pre",{className:"bg-red-50 text-red-700 rounded p-2 text-xs font-mono overflow-auto max-h-40 whitespace-pre-wrap",children:o.error}):"—"]];return(0,t.jsxs)("div",{className:"space-y-5 max-w-3xl",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between",children:[(0,t.jsxs)("div",{className:"flex items-center gap-3",children:[(0,t.jsxs)("button",{onClick:()=>n.push(`/task?task_name=${encodeURIComponent(o.task_name)}`),className:"text-sm text-gray-500 hover:text-indigo-600",children:["← ",o.task_name]}),(0,t.jsx)("span",{className:"text-gray-300",children:"/"}),(0,t.jsx)("h1",{className:"text-lg font-semibold text-gray-800",children:"Job Detail"})]}),(0,t.jsxs)("div",{className:"flex gap-2",children:[("FAILURE"===o.status||"STOPPED"===o.status||"SUCCESS"===o.status)&&(0,t.jsx)("button",{onClick:h,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium",children:"🔄 Retry"}),("QUEUEING"===o.status||"RETRYING"===o.status)&&(0,t.jsx)("button",{onClick:h,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 disabled:opacity-50 font-medium",children:"⏹ Stop"}),(0,t.jsx)("button",{onClick:f,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg border border-red-300 bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50",children:"Delete"})]})]}),(0,t.jsx)("div",{className:"bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden",children:(0,t.jsx)("table",{className:"w-full text-sm",children:(0,t.jsx)("tbody",{className:"divide-y divide-gray-100",children:y.map(([e,a])=>(0,t.jsxs)("tr",{children:[(0,t.jsx)("td",{className:"px-5 py-3 font-semibold text-gray-600 w-36 align-top",children:e}),(0,t.jsx)("td",{className:"px-5 py-3 text-gray-800",children:a})]},e))})})}),(0,t.jsx)("p",{className:"text-xs text-gray-400 text-center",children:"Auto-refreshes every 5 seconds"})]})}e.s(["default",0,function(){return(0,t.jsx)(a.Suspense,{children:(0,t.jsx)(n,{})})}])}]);
(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,18566,(e,t,a)=>{t.exports=e.r(76562)},59513,e=>{"use strict";async function t(e,t){let a=await fetch("http://localhost:8080/graphql",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:e,variables:t}),cache:"no-store"});if(!a.ok)throw Error(`GraphQL request failed: ${a.status}`);let r=await a.json();if(r.errors?.length)throw Error(r.errors[0].message);return r.data}let a=`
  query GetAllTask {
    get_all_task {
      name module_name total_jobs
      detail { queueing retrying success failure stopped }
    }
  }
`,r=`
  query GetAllJob($filter: GetAllJobInputResolver) {
    get_all_job(filter: $filter) {
      meta { page limit total_pages total_records }
      data {
        id task_name arguments retries max_retry interval
        status error result trace_id created_at finished_at
      }
    }
  }
`,s=`
  query GetCountJob($filter: GetAllJobInputResolver) {
    get_count_job(filter: $filter)
  }
`,l=`
  subscription ListenTaskDashboard($page: Int!, $limit: Int!, $search: String) {
    listen_task_dashboard(page: $page, limit: $limit, search: $search) {
      meta { page limit total_pages total_records }
      data {
        name module_name total_jobs is_loading
        detail { queueing retrying success failure stopped }
      }
    }
  }
`,i=`
  subscription ListenAllJob($filter: GetAllJobInputResolver) {
    listen_all_job(filter: $filter) {
      meta { page limit total_pages total_records }
      data {
        id task_name arguments retries max_retry interval
        status error result trace_id created_at finished_at
      }
    }
  }
`,o=`
  mutation AddJob($param: AddJobInputResolver!) {
    add_job(param: $param)
  }
`,n=`
  mutation RetryJob($job_id: String!) {
    retry_job(job_id: $job_id)
  }
`,d=`
  mutation StopJob($job_id: String!) {
    stop_job(job_id: $job_id)
  }
`,c=`
  mutation StopAllJob($task_name: String!) {
    stop_all_job(task_name: $task_name)
  }
`,u=`
  mutation RetryAllJob($filter: FilterMutateJobInputResolver!) {
    retry_all_job(filter: $filter)
  }
`,m=`
  mutation CleanJob($filter: FilterMutateJobInputResolver!) {
    clean_job(filter: $filter)
  }
`,b=`
  mutation DeleteJob($job_id: String!) {
    delete_job(job_id: $job_id)
  }
`;e.s(["ADD_JOB",0,o,"CLEAN_JOB",0,m,"DELETE_JOB",0,b,"GET_ALL_JOB",0,r,"GET_ALL_TASK",0,a,"GET_COUNT_JOB",0,s,"RETRY_ALL_JOB",0,u,"RETRY_JOB",0,n,"STATUS_COLORS",0,{QUEUEING:"bg-gray-100 text-gray-700",RETRYING:"bg-blue-100 text-blue-700",SUCCESS:"bg-green-100 text-green-700",FAILURE:"bg-red-100 text-red-700",STOPPED:"bg-yellow-100 text-yellow-700"},"STOP_ALL_JOB",0,c,"STOP_JOB",0,d,"SUBSCRIBE_ALL_JOB",0,i,"SUBSCRIBE_TASK_DASHBOARD",0,l,"canRetry",0,e=>"FAILURE"===e||"STOPPED"===e,"canStop",0,e=>"QUEUEING"===e||"RETRYING"===e,"gql",0,t])},54806,e=>{"use strict";var t=e.i(43476),a=e.i(71645),r=e.i(18566),s=e.i(59513);function l(){let e=(0,r.useSearchParams)(),l=(0,r.useRouter)(),i=e.get("id")??"",[o,n]=(0,a.useState)(null),[d,c]=(0,a.useState)(!0),[u,m]=(0,a.useState)(null),[b,_]=(0,a.useState)(!1),p=(0,a.useCallback)(async()=>{if(i)try{let e=await (0,s.gql)(s.GET_ALL_JOB,{filter:{job_id:i,limit:1}});n(e.get_all_job.data[0]??null),m(null)}catch(e){m(e instanceof Error?e.message:"Failed to load job")}finally{c(!1)}},[i]);async function g(){if(o){_(!0);try{await (0,s.gql)(s.RETRY_JOB,{job_id:o.id}),await p()}finally{_(!1)}}}async function x(){if(o){_(!0);try{await (0,s.gql)(s.STOP_JOB,{job_id:o.id}),await p()}finally{_(!1)}}}async function h(){if(o&&confirm("Permanently delete this job?")){_(!0);try{await (0,s.gql)(s.DELETE_JOB,{job_id:o.id}),l.push(`/task?task_name=${encodeURIComponent(o.task_name)}`)}finally{_(!1)}}}if((0,a.useEffect)(()=>{p();let e=setInterval(p,5e3);return()=>clearInterval(e)},[p]),d)return(0,t.jsx)("div",{className:"p-12 text-center text-gray-400",children:"Loading…"});if(u)return(0,t.jsx)("div",{className:"p-12 text-center text-red-500",children:u});if(!o)return(0,t.jsx)("div",{className:"p-12 text-center text-gray-400",children:"Job not found"});function f(e){try{return JSON.stringify(JSON.parse(e),null,2)}catch{return e}}let y=[["ID",(0,t.jsx)("span",{className:"font-mono text-sm break-all",children:o.id})],["Task Name",(0,t.jsx)("button",{onClick:()=>l.push(`/task?task_name=${encodeURIComponent(o.task_name)}`),className:"text-indigo-600 hover:underline font-mono font-medium",children:o.task_name})],["Status",(0,t.jsx)("span",{className:`px-2 py-0.5 rounded text-xs font-semibold ${s.STATUS_COLORS[o.status]??"bg-gray-100 text-gray-600"}`,children:o.status})],["Retries",`${o.retries} / ${o.max_retry}`],["Interval",o.interval||"—"],["Created At",o.created_at?new Date(o.created_at).toLocaleString():"—"],["Finished At",o.finished_at?new Date(o.finished_at).toLocaleString():"—"],["Trace ID",o.trace_id||"—"],["Arguments",(0,t.jsx)("pre",{className:"bg-gray-50 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap border border-gray-200",children:f(o.arguments)})],...o.result?[["Result",(0,t.jsx)("pre",{className:"bg-gray-50 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap border border-gray-200",children:f(o.result)})]]:[],...o.error?[["Last Error",(0,t.jsx)("pre",{className:"bg-red-50 text-red-700 rounded-lg p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap border border-red-200",children:o.error})]]:[]];return(0,t.jsxs)("div",{className:"space-y-5 max-w-3xl",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between flex-wrap gap-3",children:[(0,t.jsxs)("div",{className:"flex items-center gap-2 text-sm",children:[(0,t.jsxs)("button",{onClick:()=>l.push(`/task?task_name=${encodeURIComponent(o.task_name)}`),className:"text-gray-500 hover:text-indigo-600",children:["← ",o.task_name]}),(0,t.jsx)("span",{className:"text-gray-300",children:"/"}),(0,t.jsx)("span",{className:"font-semibold text-gray-800",children:"Job Detail"})]}),(0,t.jsxs)("div",{className:"flex gap-2",children:[(0,s.canRetry)(o.status)&&(0,t.jsx)("button",{onClick:g,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium",children:"🔄 Retry"}),(0,s.canStop)(o.status)&&(0,t.jsx)("button",{onClick:x,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 disabled:opacity-50 font-medium",children:"⏹ Stop"}),(0,t.jsx)("button",{onClick:h,disabled:b,className:"text-sm px-4 py-1.5 rounded-lg border border-red-300 bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-50",children:"🗑 Delete"})]})]}),(0,t.jsx)("div",{className:"bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden",children:(0,t.jsx)("table",{className:"w-full text-sm",children:(0,t.jsx)("tbody",{className:"divide-y divide-gray-100",children:y.map(([e,a])=>(0,t.jsxs)("tr",{children:[(0,t.jsx)("td",{className:"px-5 py-3 font-semibold text-gray-500 w-32 align-top whitespace-nowrap",children:e}),(0,t.jsx)("td",{className:"px-5 py-3 text-gray-800",children:a})]},e))})})}),(0,t.jsx)("p",{className:"text-xs text-gray-400 text-center",children:"Auto-refreshes every 5 seconds"})]})}e.s(["default",0,function(){return(0,t.jsx)(a.Suspense,{children:(0,t.jsx)(l,{})})}])}]);
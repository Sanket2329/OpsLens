import { createServer } from "vite";
createServer({})
  .then((s) => s.listen())
  .then(() => console.log("started"));

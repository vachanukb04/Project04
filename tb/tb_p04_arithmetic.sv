`timescale 1ns/1ps
`default_nettype none

module tb_p04_arithmetic;
    logic clk = 1'b0;
    always #5 clk = ~clk;
    logic rst_n = 1'b0;

    logic d_iv = 0, d_or = 0;
    wire d_ir, d_ov, d_overflow;
    logic [31:0] d_a = 0, d_b = 0;
    logic signed [31:0] d_acc = 0;
    wire signed [31:0] d_result;
    p04_dot4 u_dot4 (
        .clk(clk), .rst_n(rst_n), .i_valid(d_iv), .i_ready(d_ir),
        .i_a(d_a), .i_b(d_b), .i_acc(d_acc),
        .o_valid(d_ov), .o_ready(d_or), .o_result(d_result),
        .o_overflow(d_overflow)
    );

    logic s_iv = 0, s_or = 0;
    wire s_ir, s_ov;
    logic [7:0] s_mask = 0;
    logic [255:0] s_a = 0, s_b = 0, s_acc = 0;
    wire [7:0] s_omask, s_overflow;
    wire [255:0] s_result;
    p04_simd_dot4 u_simd (
        .clk(clk), .rst_n(rst_n), .i_valid(s_iv), .i_ready(s_ir),
        .i_mask(s_mask), .i_a(s_a), .i_b(s_b), .i_acc(s_acc),
        .o_valid(s_ov), .o_ready(s_or), .o_mask(s_omask),
        .o_result(s_result), .o_overflow(s_overflow)
    );

    logic q_iv = 0, q_or = 0;
    wire q_ir, q_ov, q_error;
    logic signed [31:0] q_acc = 0;
    logic [30:0] q_multiplier = 0;
    logic [5:0] q_shift = 0;
    logic signed [7:0] q_zp = 0, q_min = -128, q_max = 127;
    wire signed [7:0] q_result;
    p04_requantize u_requant (
        .clk(clk), .rst_n(rst_n), .i_valid(q_iv), .i_ready(q_ir),
        .i_acc(q_acc), .i_multiplier(q_multiplier), .i_shift(q_shift),
        .i_zero_point(q_zp), .i_clamp_min(q_min), .i_clamp_max(q_max),
        .o_valid(q_ov), .o_ready(q_or), .o_result(q_result), .o_error(q_error)
    );

    // Independent wide-integer references; not instantiated RTL copies.
    function automatic longint signed dot_reference(
        input logic [31:0] a, input logic [31:0] b,
        input logic signed [31:0] acc
    );
        longint signed result, av, bv;
        begin
            result = longint'(acc);
            for (int k = 0; k < 4; k = k + 1) begin
                av = longint'($signed(a[k*8 +: 8]));
                bv = longint'($signed(b[k*8 +: 8]));
                result = result + av * bv;
            end
            return result;
        end
    endfunction

    function automatic logic signed [7:0] requant_reference(
        input logic signed [31:0] acc,
        input logic [30:0] multiplier,
        input logic [5:0] shift,
        input logic signed [7:0] zp, lo, hi
    );
        longint signed a, m, product, value;
        longint unsigned magnitude, divisor, quotient, remainder;
        begin
            if (lo > hi) return 8'sd0;
            a = longint'(acc);
            m = longint'($signed({1'b0, multiplier}));
            product = a * m;
            magnitude = (product < 0) ? $unsigned(-product) : $unsigned(product);
            divisor = 64'd1 << shift;
            // Quotient/remainder rounding is independent of the DUT's add/shift.
            quotient = magnitude / divisor;
            remainder = magnitude % divisor;
            if ((remainder != 0) && (remainder >= divisor - remainder))
                quotient = quotient + 1;
            value = (product < 0) ? -$signed(quotient) : $signed(quotient);
            value = value + longint'(zp);
            if (value < lo) return lo;
            if (value > hi) return hi;
            return $signed(value[7:0]);
        end
    endfunction

    logic [31:0] rng = 32'hc0ffee04;
    function automatic logic [31:0] rand32();
        begin
            rng = rng ^ (rng << 13);
            rng = rng ^ (rng >> 17);
            rng = rng ^ (rng << 5);
            return rng;
        end
    endfunction

    bit d_pending = 0, s_pending = 0, q_pending = 0;
    bit d_hold = 0, s_hold = 0, q_hold = 0;
    logic signed [31:0] d_expected = 0;
    logic d_expected_overflow = 0;
    logic [255:0] s_expected = 0;
    logic [7:0] s_expected_overflow = 0, s_expected_mask = 0;
    logic signed [7:0] q_expected = 0;
    logic q_expected_error = 0;
    longint signed wide;
    int dot_accepted = 0, simd_accepted = 0, requant_accepted = 0;
    int dot_stalls = 0, simd_stalls = 0, requant_stalls = 0;
    int overflow_seen = 0, config_error_seen = 0, masked_seen = 0;
    int reset_pending_seen = 0, exhaustive_accepted = 0;

    initial begin
        if ($test$plusargs("WAVES")) begin
            $dumpfile("p04_arithmetic.vcd");
            $dumpvars(0, tb_p04_arithmetic);
        end

        // 1024 directed/random cycles, drain, all 65536 byte pairs, drain.
        for (int cycle = 0; cycle < 66600; cycle = cycle + 1) begin
            @(negedge clk);
            rst_n = !((cycle < 2) || (cycle == 27) || (cycle == 28)
                    || (cycle == 197));
            d_or = (rand32() % 4 != 0);
            s_or = (rand32() % 3 != 0);
            q_or = (rand32() % 4 != 0);
            if (cycle < 18) begin d_or = 1; s_or = 1; q_or = 1; end
            if ((cycle >= 20) && (cycle <= 27)) begin
                d_or = 0; s_or = 0; q_or = 0;
            end

            // A source holds its request until accepted, including under stalls.
            if ((cycle < 1024) && (!d_hold || !rst_n)) begin
                d_iv = (rand32() % 5 != 0);
                d_a = rand32(); d_b = rand32(); d_acc = $signed(rand32());
                if (cycle < 18) d_iv = 1;
                case (cycle)
                    2: begin d_a = 32'h80808080; d_b = 32'h80808080; d_acc = 32'sh7fffffff; end
                    3: begin d_a = 32'h80808080; d_b = 32'h7f7f7f7f; d_acc = 32'sh80000000; end
                    4: begin d_a = 32'h80808080; d_b = 32'h80808080; d_acc = 32'sh80000000; end
                    5: begin d_a = 32'h7f7f7f7f; d_b = 32'h7f7f7f7f; d_acc = 32'sh7fffffff; end
                    6: begin d_a = 0; d_b = 32'hffffffff; d_acc = 32'sh80000000; end
                    default: begin end
                endcase
            end
            if ((cycle < 1024) && (!s_hold || !rst_n)) begin
                s_iv = (rand32() % 5 != 0);
                s_mask = 8'(rand32());
                for (int lane = 0; lane < 8; lane = lane + 1) begin
                    s_a[lane*32 +: 32] = rand32();
                    s_b[lane*32 +: 32] = rand32();
                    s_acc[lane*32 +: 32] = rand32();
                end
                if (cycle < 18) begin
                    s_iv = 1;
                    s_mask = (cycle == 12) ? 8'h00 : 8'hff;
                    for (int lane = 0; lane < 8; lane = lane + 1) begin
                        s_a[lane*32 +: 32] = 32'h80808080;
                        s_b[lane*32 +: 32] = 32'h80808080;
                        s_acc[lane*32 +: 32] = (lane % 2 == 0)
                            ? 32'h7fffffff : 32'h80000000;
                    end
                end
            end
            if ((cycle < 1024) && (!q_hold || !rst_n)) begin
                q_iv = (rand32() % 5 != 0);
                q_acc = $signed(rand32());
                q_multiplier = 31'(rand32());
                q_shift = 6'($unsigned(cycle));
                q_zp = $signed(8'(rand32())); q_min = -128; q_max = 127;
                if (cycle < 18) begin
                    q_iv = 1; q_acc = 1; q_multiplier = 1; q_shift = 1; q_zp = 0;
                    case (cycle)
                        3: q_acc = -1;
                        4: q_acc = 3;
                        5: q_acc = -3;
                        6: begin q_acc = 32'sh7fffffff; q_multiplier = 31'h7fffffff; q_shift = 0; end
                        7: begin q_acc = 32'sh80000000; q_multiplier = 31'h7fffffff; q_shift = 0; end
                        8: begin q_acc = 32'sh80000000; q_multiplier = 31'h7fffffff; q_shift = 63; end
                        9: begin q_acc = 32'sh80000000; q_multiplier = 0; q_zp = 127; end
                        10: begin q_min = 12; q_max = -12; end
                        11: begin q_min = 4; q_max = 4; end
                        12: begin q_acc = -8; q_min = 0; end
                        13: begin q_acc = 0; q_zp = -128; end
                        14: begin q_acc = 1; q_multiplier = 1; q_shift = 63; end
                        15: begin q_acc = -1; q_multiplier = 1; q_shift = 0; end
                        default: begin end
                    endcase
                end
            end

            if (cycle >= 1024) begin
                // Stop random traffic and flush before exhaustive scalar tests.
                d_or = 1; s_or = 1; q_or = 1;
                if (!d_hold) d_iv = 0;
                if (!s_hold) s_iv = 0;
                if (!q_hold) q_iv = 0;
                if ((cycle >= 1056) && (cycle < 66592)) begin
                    d_iv = 1;
                    d_a = $unsigned((cycle - 1056) % 256);
                    d_b = $unsigned((cycle - 1056) / 256);
                    d_acc = 0;
                end
            end
            #1;
            if (d_ir !== (rst_n && (!d_pending || d_or)))
                $fatal(1, "DOT4 ready mismatch at cycle %0d", cycle);
            if (s_ir !== (rst_n && (!s_pending || s_or)))
                $fatal(1, "SIMD ready mismatch at cycle %0d", cycle);
            if (q_ir !== (rst_n && (!q_pending || q_or)))
                $fatal(1, "REQUANT ready mismatch at cycle %0d", cycle);

            if (!rst_n) begin
                if (d_pending || s_pending || q_pending) reset_pending_seen++;
                d_pending = 0; s_pending = 0; q_pending = 0;
                d_hold = 0; s_hold = 0; q_hold = 0;
            end else begin
                if (d_pending && !d_or) dot_stalls++;
                if (s_pending && !s_or) simd_stalls++;
                if (q_pending && !q_or) requant_stalls++;
                if (d_ir) begin
                    d_pending = d_iv;
                    if (d_iv) begin
                        wide = dot_reference(d_a, d_b, d_acc);
                        d_expected = $signed(wide[31:0]);
                        d_expected_overflow = (wide > 64'sd2147483647)
                                            || (wide < -64'sd2147483648);
                        dot_accepted++;
                        if (d_expected_overflow) overflow_seen++;
                        if ((cycle >= 1056) && (cycle < 66592)) exhaustive_accepted++;
                    end
                end
                if (s_ir) begin
                    s_pending = s_iv;
                    if (s_iv) begin
                        s_expected_mask = s_mask;
                        for (int lane = 0; lane < 8; lane = lane + 1) begin
                            wide = dot_reference(s_mask[lane] ? s_a[lane*32 +: 32] : 32'b0,
                                s_b[lane*32 +: 32], $signed(s_acc[lane*32 +: 32]));
                            s_expected[lane*32 +: 32] = wide[31:0];
                            s_expected_overflow[lane] = (wide > 64'sd2147483647)
                                                    || (wide < -64'sd2147483648);
                        end
                        simd_accepted++;
                        if (s_mask != 8'hff) masked_seen++;
                    end
                end
                if (q_ir) begin
                    q_pending = q_iv;
                    if (q_iv) begin
                        q_expected = requant_reference(q_acc, q_multiplier, q_shift, q_zp, q_min, q_max);
                        q_expected_error = (q_min > q_max);
                        requant_accepted++;
                        if (q_expected_error) config_error_seen++;
                    end
                end
                d_hold = d_iv && !d_ir;
                s_hold = s_iv && !s_ir;
                q_hold = q_iv && !q_ir;
            end

            @(posedge clk);
            #1;
            if (d_ov !== d_pending || s_ov !== s_pending || q_ov !== q_pending)
                $fatal(1, "Valid/reset mismatch at cycle %0d", cycle);
            if (d_pending && ((d_result !== d_expected) || (d_overflow !== d_expected_overflow)))
                $fatal(1, "DOT4 mismatch cycle=%0d got=%h expected=%h overflow=%b/%b",
                    cycle, d_result, d_expected, d_overflow, d_expected_overflow);
            if (s_pending && ((s_result !== s_expected) || (s_overflow !== s_expected_overflow)
                          || (s_omask !== s_expected_mask)))
                $fatal(1, "SIMD mismatch at cycle %0d", cycle);
            if (q_pending && ((q_result !== q_expected) || (q_error !== q_expected_error)))
                $fatal(1, "REQUANT mismatch cycle=%0d got=%0d expected=%0d error=%b/%b",
                    cycle, q_result, q_expected, q_error, q_expected_error);
            if (!rst_n && ((d_result !== 0) || (d_overflow !== 0)
                        || (s_result !== 0) || (s_omask !== 0) || (s_overflow !== 0)
                        || (q_result !== 0) || (q_error !== 0)))
                $fatal(1, "Reset data mismatch at cycle %0d", cycle);
        end

        if (d_pending || s_pending || q_pending)
            $fatal(1, "Regression ended without draining pending results");
        if ((exhaustive_accepted != 65536) || (simd_accepted < 100) || (requant_accepted < 100)
         || (dot_stalls == 0) || (simd_stalls == 0) || (requant_stalls == 0)
         || (overflow_seen == 0) || (config_error_seen == 0)
         || (masked_seen == 0) || (reset_pending_seen == 0))
            $fatal(1, "Required coverage condition was not exercised");
        $display("PASS Project04 arithmetic regression");
        $display("accepted dot4=%0d simd=%0d requant=%0d exhaustive_byte_pairs=%0d",
            dot_accepted, simd_accepted, requant_accepted, exhaustive_accepted);
        $display("stalls dot4=%0d simd=%0d requant=%0d overflow_cases=%0d config_errors=%0d masked_vectors=%0d reset_pending=%0d",
            dot_stalls, simd_stalls, requant_stalls, overflow_seen,
            config_error_seen, masked_seen, reset_pending_seen);
        $finish;
    end

    initial begin
        #1000000;
        $fatal(1, "Watchdog timeout");
    end
endmodule

`default_nettype wire
